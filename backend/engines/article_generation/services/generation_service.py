"""
Article Generation Service

RAG-based article generation using GROQ.
"""

import structlog
from typing import List, Dict, Any
from django.db import transaction
from django.utils import timezone
from groq import Groq
from django.conf import settings

from engines.content.models import Chunk
from engines.knowledge.models import Topic, ChunkTopicMap
from ..models import Article, ArticleSourceMap, ArticleGenerationJob

logger = structlog.get_logger(__name__)


# GROQ Configuration
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_TEMPERATURE = 0.7
GROQ_MAX_TOKENS = 2000

# Article specs
TARGET_WORD_COUNT = 1000
MIN_WORD_COUNT = 500
MAX_WORD_COUNT = 1500


class ArticleGenerationService:
    """Service for generating articles from chunks using RAG."""
    
    @staticmethod
    def generate_article(
        topic_id: str,
        include_ca: bool = False,
        user_id: int = None
    ) -> Dict[str, Any]:
        """
        Generate article for a topic using RAG pipeline.
        
        Args:
            topic_id: UUID of topic
            include_ca: Whether to include current affairs chunks
            user_id: User requesting generation (optional)
        
        Returns:
            Dict with article data and metadata
        """
        logger.info("article_generation_started", topic_id=topic_id, include_ca=include_ca)
        
        try:
            # Get topic
            topic = Topic.objects.get(id=topic_id)
            
            # Fetch mapped chunks
            chunks = ArticleGenerationService._fetch_chunks(topic, include_ca)
            
            if not chunks:
                logger.warning("no_chunks_found", topic_id=topic_id)
                raise ValueError(f"No chunks mapped to topic: {topic.name}")
            
            logger.info("chunks_fetched", topic_id=topic_id, chunk_count=len(chunks))
            
            # Assemble RAG context
            context = ArticleGenerationService._assemble_context(chunks, include_ca)
            
            # Generate article content
            article_data = ArticleGenerationService._generate_with_groq(
                topic=topic,
                context=context,
                include_ca=include_ca
            )
            
            # Validate quality
            quality_score = ArticleGenerationService._validate_quality(article_data)
            article_data['quality_score'] = quality_score
            
            # Store article + source map
            article = ArticleGenerationService._store_article(
                topic=topic,
                article_data=article_data,
                chunks=chunks,
                user_id=user_id
            )
            
            logger.info(
                "article_generated_successfully",
                topic_id=topic_id,
                article_id=str(article.id),
                word_count=article.word_count,
                quality_score=quality_score
            )
            
            return {
                'success': True,
                'article_id': str(article.id),
                'title': article.title,
                'word_count': article.word_count,
                'quality_score': quality_score,
                'source_chunks': len(chunks),
            }
        
        except Topic.DoesNotExist:
            logger.error("topic_not_found", topic_id=topic_id)
            raise
        
        except Exception as e:
            logger.error("article_generation_failed", topic_id=topic_id, error=str(e))
            raise
    
    @staticmethod
    def _fetch_chunks(topic: Topic, include_ca: bool) -> List[Chunk]:
        """
        Fetch chunks mapped to topic.
        
        Returns chunks ordered by relevance score (highest first).
        """
        # Get all mappings for this topic
        mappings = ChunkTopicMap.objects.filter(
            topic=topic
        ).select_related('chunk').order_by('-relevance_score')
        
        chunks = []
        for mapping in mappings:
            chunk = mapping.chunk
            
            # Filter by source type if needed
            if not include_ca and chunk.source_type == 'dynamic':
                continue
            
            chunks.append(chunk)
        
        logger.debug(
            "chunks_filtered",
            topic_id=str(topic.id),
            total_chunks=len(chunks),
            include_ca=include_ca
        )
        
        return chunks
    
    @staticmethod
    def _assemble_context(chunks: List[Chunk], include_ca: bool) -> str:
        """
        Assemble RAG context from chunks.
        
        Separates static and CA chunks for better prompt structure.
        """
        if not include_ca:
            # Simple concatenation for static-only
            context_parts = []
            for idx, chunk in enumerate(chunks, 1):
                context_parts.append(f"[Source {idx}]")
                context_parts.append(chunk.chunk_text)
                context_parts.append("---")
            
            return "\n".join(context_parts)
        
        else:
            # Separate static and CA
            static_chunks = [c for c in chunks if c.source_type == 'static']
            ca_chunks = [c for c in chunks if c.source_type == 'dynamic']
            
            context = "=== THEORETICAL FOUNDATION (Textbook Content) ===\n\n"
            
            for idx, chunk in enumerate(static_chunks, 1):
                context += f"[Source {idx}]\n{chunk.chunk_text}\n\n"
            
            if ca_chunks:
                context += "\n=== CURRENT CONTEXT (Recent Developments) ===\n\n"
                for idx, chunk in enumerate(ca_chunks, 1):
                    context += f"[CA Source {idx}]\n{chunk.chunk_text}\n\n"
            
            return context
    
    @staticmethod
    def _generate_with_groq(
        topic: Topic,
        context: str,
        include_ca: bool
    ) -> Dict[str, Any]:
        """
        Generate article using GROQ API.
        
        Returns article data with title, content, summary.
        """
        # Build prompt
        prompt = ArticleGenerationService._build_prompt(topic, context, include_ca)
        
        logger.info(
            "calling_groq",
            topic_id=str(topic.id),
            model=GROQ_MODEL,
            context_length=len(context)
        )
        
        # Call GROQ
        client = Groq(api_key=settings.GROQ_API_KEY)
        
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=GROQ_TEMPERATURE,
            max_tokens=GROQ_MAX_TOKENS
        )
        
        content = response.choices[0].message.content
        
        # Extract title and content
        article_data = ArticleGenerationService._parse_groq_output(content)
        
        # Calculate word count
        article_data['word_count'] = len(article_data['content'].split())
        
        logger.debug(
            "groq_generation_completed",
            word_count=article_data['word_count'],
            has_summary=bool(article_data.get('summary'))
        )
        
        return article_data
    
    @staticmethod
    def _build_prompt(topic: Topic, context: str, include_ca: bool) -> str:
        """Build GROQ prompt for article generation."""
        
        if not include_ca:
            prompt = f"""You are an expert UPSC educator writing for IAS aspirants.

Generate a comprehensive article on: {topic.name}

Topic Description: {topic.description}

Source Material:
{context}

Requirements:
1. Structure: Introduction (100-150 words), Body (600-700 words), Conclusion (100-150 words)
2. UPSC Focus: Connect theory to exam patterns (Prelims + Mains)
3. Examples: Use concrete examples from source material
4. Clarity: Clear explanations suitable for UPSC preparation
5. Depth: Cover all important aspects mentioned in sources
6. Format: Use proper paragraphs (no bullet points in body)

Target Length: {TARGET_WORD_COUNT} words

Generate the article now:"""
        
        else:
            prompt = f"""You are an expert UPSC educator writing for IAS aspirants.

Generate a comprehensive article integrating THEORY and CURRENT AFFAIRS on: {topic.name}

Topic Description: {topic.description}

Source Material:
{context}

Requirements:
1. Structure: 
   - Introduction (100-150 words) - Set context
   - Theoretical Framework (400-500 words) - Core concepts from textbooks
   - Current Developments (200-300 words) - Recent news/events
   - Analysis & Exam Relevance (200-250 words) - Connect theory to practice
   - Conclusion (100-150 words) - UPSC perspective

2. Integration: Show how current affairs relate to theoretical concepts
3. UPSC Angle: Highlight prelims facts + mains discussion points
4. Examples: Use both theoretical and current examples
5. Clarity: Accessible to UPSC aspirants
6. Format: Proper paragraphs (no bullet points)

Target Length: {TARGET_WORD_COUNT} words

Generate the integrated article now:"""
        
        return prompt
    
    @staticmethod
    def _parse_groq_output(content: str) -> Dict[str, Any]:
        """
        Parse GROQ output to extract title, content, summary.
        
        If GROQ includes a title in output, extract it.
        Otherwise, use first line as title.
        """
        lines = content.strip().split('\n')
        
        # Try to detect title (first line if short, or explicitly marked)
        title = None
        content_start = 0
        
        if len(lines) > 0:
            first_line = lines[0].strip()
            
            # Check if first line is title-like (short, no period at end)
            if len(first_line) < 100 and not first_line.endswith('.'):
                title = first_line.replace('#', '').strip()
                content_start = 1
        
        # Get content (skip title if found)
        article_content = '\n'.join(lines[content_start:]).strip()
        
        # Extract summary (first paragraph or generate from first 150 words)
        paragraphs = article_content.split('\n\n')
        summary = ''
        
        if paragraphs:
            first_para = paragraphs[0].strip()
            summary = ' '.join(first_para.split()[:30])  # First 30 words
        
        return {
            'title': title,
            'content': article_content,
            'summary': summary,
        }
    
    @staticmethod
    def _validate_quality(article_data: Dict[str, Any]) -> float:
        """
        Validate article quality.
        
        Returns quality score 0-100.
        """
        checks = {}
        
        # Word count check
        word_count = article_data.get('word_count', 0)
        checks['word_count'] = MIN_WORD_COUNT <= word_count <= MAX_WORD_COUNT
        
        # Has content
        checks['has_content'] = len(article_data.get('content', '')) > 100
        
        # Has summary
        checks['has_summary'] = len(article_data.get('summary', '')) > 20
        
        # Proper structure (multiple paragraphs)
        content = article_data.get('content', '')
        checks['proper_structure'] = content.count('\n\n') >= 3
        
        # Not too repetitive (unique words ratio)
        words = content.split()
        if words:
            unique_ratio = len(set(words)) / len(words)
            checks['not_repetitive'] = unique_ratio > 0.4
        else:
            checks['not_repetitive'] = False
        
        # Calculate score
        score = (sum(checks.values()) / len(checks)) * 100
        
        logger.debug("quality_validation", score=score, checks=checks)
        
        return round(score, 2)
    
    @staticmethod
    @transaction.atomic
    def _store_article(
        topic: Topic,
        article_data: Dict[str, Any],
        chunks: List[Chunk],
        user_id: int = None
    ) -> Article:
        """
        Store article and create source maps.
        
        Atomic transaction ensures article + mappings created together.
        """
        # Generate title if not provided
        title = article_data.get('title') or f"{topic.name}: Comprehensive Guide"
        
        # Create article
        article = Article.objects.create(
            title=title,
            content=article_data['content'],
            summary=article_data.get('summary', ''),
            topic=topic,
            word_count=article_data['word_count'],
            generation_type='ai_generated',
            quality_score=article_data['quality_score'],
            review_status='pending' if article_data['quality_score'] < 70 else 'approved',
            generation_metadata={
                'chunks_used': len(chunks),
                'static_chunks': len([c for c in chunks if c.source_type == 'static']),
                'ca_chunks': len([c for c in chunks if c.source_type == 'dynamic']),
                'model': GROQ_MODEL,
                'temperature': GROQ_TEMPERATURE,
            }
        )
        
        # Create source maps
        for idx, chunk in enumerate(chunks, 1):
            # Get relevance from ChunkTopicMap
            mapping = ChunkTopicMap.objects.filter(
                chunk=chunk,
                topic=topic
            ).first()
            
            relevance_weight = mapping.relevance_score if mapping else 1.0
            
            ArticleSourceMap.objects.create(
                article=article,
                chunk=chunk,
                relevance_weight=relevance_weight,
                sequence_order=idx,
            )
        
        logger.info(
            "article_stored",
            article_id=str(article.id),
            source_maps_created=len(chunks)
        )
        
        return article

        