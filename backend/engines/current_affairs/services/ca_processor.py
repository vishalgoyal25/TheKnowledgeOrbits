import sentry_sdk
from typing import List
from django.db import transaction
from django.utils import timezone
import structlog

from engines.content.models import Embedding
from engines.content.services.embedding_service import EmbeddingService
from ..models import CAArticle, CAChunk

logger = structlog.get_logger(__name__)


class CAProcessorService:
    """CA article processing service"""

    CHUNK_SIZE = 1200
    CHUNK_OVERLAP = 200
    MIN_CHUNK_SIZE = 20

    @staticmethod
    def process_article(article: CAArticle) -> bool:
        """Process a single CA article into chunks"""
        logger.info(
            "processing_ca_article_start",
            title=article.title,
            article_id=str(article.id),
        )

        try:
            article.processing_status = "processing"
            article.save()

            chunks_data = CAProcessorService._chunk_content(article.content)
            if not chunks_data and article.content and len(article.content) > 10:
                chunks_data = [article.content.strip()]

            if not chunks_data:
                msg = (
                    f"No valid chunks generated. Content length: {len(article.content)}"
                )
                logger.warning("no_valid_chunks_generated", article_id=str(article.id))
                article.processing_status = "failed"
                article.processing_error = msg
                article.save()
                return False

            # Create chunks with embeddings
            with transaction.atomic():
                chunks_created = []

                # Perform batch embedding to save API calls/Time
                embedding_vectors = EmbeddingService.generate_embeddings_batch(
                    chunks_data
                )

                for idx, (chunk_text, vector) in enumerate(
                    zip(chunks_data, embedding_vectors)
                ):
                    # 1. Create chunk first to get ID
                    chunk = CAChunk.objects.create(
                        ca_article=article,
                        chunk_text=chunk_text,
                        chunk_index=idx,
                        source_type="dynamic",
                        published_at=article.published_at,
                        quality_flag="medium",
                        confidence_score=0.7,
                        embedding_id=None,
                    )

                    # 2. Create embedding record with chunk ID
                    embedding = Embedding.objects.create(
                        content_type="ca_chunk",
                        content_id=chunk.id,
                        vector=vector,
                        model_name=EmbeddingService.MODEL_NAME,
                    )

                    # 3. Update chunk with embedding ID
                    chunk.embedding_id = embedding.id
                    chunk.save()
                    chunks_created.append(chunk)

                article.chunk_count = len(chunks_created)
                article.processing_status = "completed"
                article.processed_at = timezone.now()
                article.save()

            logger.info("processing_ca_article_completed", article_id=str(article.id))
            return True

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(
                "failed_to_process_ca_article", error=str(e), article_id=str(article.id)
            )
            article.processing_status = "failed"
            article.processing_error = str(e)
            article.save()
            return False

    @staticmethod
    def _chunk_content(content: str) -> List[str]:
        """Chunk content into ~1200 char pieces with overlap"""
        if not content:
            return []
        chunks = []
        start = 0
        content_length = len(content)

        if content_length < CAProcessorService.CHUNK_SIZE:
            if (
                content_length >= CAProcessorService.MIN_CHUNK_SIZE
                or content_length > 10
            ):
                return [content]
            return []

        while start < content_length:
            end = start + CAProcessorService.CHUNK_SIZE
            if end < content_length:
                last_period = content.rfind(".", start, end)
                last_question = content.rfind("?", start, end)
                last_exclamation = content.rfind("!", start, end)
                break_point = max(last_period, last_question, last_exclamation)
                if break_point > start:
                    end = break_point + 1

            chunk_text = content[start:end].strip()
            if len(chunk_text) >= CAProcessorService.MIN_CHUNK_SIZE:
                chunks.append(chunk_text)
            start = end - CAProcessorService.CHUNK_OVERLAP
        return chunks

    @staticmethod
    def process_pending_articles(batch_size: int = 10) -> int:
        """Process pending CA articles in batches"""
        pending_articles = CAArticle.objects.filter(
            processing_status="pending"
        ).order_by("published_at")[:batch_size]
        processed_count = 0
        for article in pending_articles:
            if CAProcessorService.process_article(article):
                processed_count += 1
        return processed_count
