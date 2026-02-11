"""
CA Processor Service

Processes CA articles into chunks and generates embeddings
"""

import logging
from typing import List
from django.utils import timezone
from django.db import transaction
from sentence_transformers import SentenceTransformer

from ..models import CAArticle, CAChunk
from engines.content.models import Embedding

logger = logging.getLogger(__name__)

# Initialize embedding model (same as content engine)
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')


class CAProcessorService:
    """CA article processing service"""
    
    CHUNK_SIZE = 1200
    CHUNK_OVERLAP = 200
    MIN_CHUNK_SIZE = 20  # Lowered to 20 to accommodate very short RSS summaries
    
    @staticmethod
    def process_article(article: CAArticle) -> bool:
        """
        Process a single CA article into chunks
        
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Processing CA article: {article.title}", extra={
            'article_id': str(article.id)
        })
        
        try:
            article.processing_status = 'processing'
            article.save()
            
            # Chunk the content
            chunks_data = CAProcessorService._chunk_content(article.content)
            
            # If standard chunking fails but we have content, treat entire content as one chunk
            if not chunks_data and article.content and len(article.content) > 10:
                 chunks_data = [article.content.strip()]
            
            if not chunks_data:
                msg = f'No valid chunks generated. Content length: {len(article.content)}'
                logger.warning(msg)
                article.processing_status = 'failed'
                article.processing_error = msg
                article.save()
                return False
            
            # Create chunks with embeddings
            with transaction.atomic():
                chunks_created = []
                
                for idx, chunk_text in enumerate(chunks_data):
                    # Generate embedding
                    embedding_vector = embedding_model.encode(chunk_text)
                    
                    # 1. Create chunk first to get ID
                    chunk = CAChunk.objects.create(
                        ca_article=article,
                        chunk_text=chunk_text,
                        chunk_index=idx,
                        source_type='dynamic',
                        published_at=article.published_at,
                        quality_flag='medium',
                        confidence_score=0.7,
                        embedding_id=None # Will update momentarily
                    )
                    
                    # 2. Create embedding record with chunk ID
                    embedding = Embedding.objects.create(
                        content_type='ca_chunk',
                        content_id=chunk.id, 
                        vector=embedding_vector.tolist(),
                        model_name='all-MiniLM-L6-v2'
                    )
                    
                    # 3. Update chunk with embedding ID
                    chunk.embedding_id = embedding.id
                    chunk.save()
                    
                    chunks_created.append(chunk)
                
                # Update article
                article.chunk_count = len(chunks_created)
                article.processing_status = 'completed'
                article.processing_error = ''
                article.processed_at = timezone.now()
                article.save()
            
            logger.info(f"Processed CA article: {len(chunks_created)} chunks", extra={
                'article_id': str(article.id)
            })
            
            return True
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"CRITICAL ERROR processing {article.id}: {e}")
            logger.error(f"Failed to process CA article: {e}", extra={
                'article_id': str(article.id)
            })
            
            article.processing_status = 'failed'
            article.processing_error = str(e)
            article.save()
            
            return False
    
    @staticmethod
    def _chunk_content(content: str) -> List[str]:
        """
        Chunk content into ~1200 char pieces with overlap
        """
        if not content:
            return []

        chunks = []
        start = 0
        content_length = len(content)
        
        # If content is short, just return it as one chunk if above min size
        if content_length < CAProcessorService.CHUNK_SIZE:
             if content_length >= CAProcessorService.MIN_CHUNK_SIZE:
                 return [content]
             # If slightly less than min size but substantial, let it pass in this update
             if content_length > 10:
                 return [content]
             return []

        while start < content_length:
            # Calculate end position
            end = start + CAProcessorService.CHUNK_SIZE
            
            # If this is not the last chunk, try to break at sentence boundary
            if end < content_length:
                # Look for sentence end markers
                last_period = content.rfind('.', start, end)
                last_question = content.rfind('?', start, end)
                last_exclamation = content.rfind('!', start, end)
                
                break_point = max(last_period, last_question, last_exclamation)
                
                if break_point > start:
                    end = break_point + 1
            
            # Extract chunk
            chunk_text = content[start:end].strip()
            
            # Only add if meets minimum size
            if len(chunk_text) >= CAProcessorService.MIN_CHUNK_SIZE:
                chunks.append(chunk_text)
            
            # Move start position (with overlap)
            start = end - CAProcessorService.CHUNK_OVERLAP
        
        return chunks
    
    @staticmethod
    def process_pending_articles(batch_size: int = 10) -> int:
        """
        Process pending CA articles in batches
        """
        pending_articles = CAArticle.objects.filter(
            processing_status='pending'
        ).order_by('published_at')[:batch_size]
        
        processed_count = 0
        
        for article in pending_articles:
            if CAProcessorService.process_article(article):
                processed_count += 1
        
        logger.info(f"Processed {processed_count}/{len(pending_articles)} pending CA articles")
        
        return processed_count
        