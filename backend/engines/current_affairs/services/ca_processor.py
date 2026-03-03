from typing import Any, Dict, List

from django.db import transaction
from django.utils import timezone

import sentry_sdk
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

            # Fix: Ensure start always moves forward.
            # If the break point was too close to start (shorter than overlap),
            # we don't overlap to avoid an infinite backward loop.
            if (end - start) <= CAProcessorService.CHUNK_OVERLAP:
                start = end
            else:
                start = end - CAProcessorService.CHUNK_OVERLAP

        return chunks

    @staticmethod
    def process_pending_articles(batch_size: int = 50) -> int:
        """
        Process pending CA articles in TRUE BATCH mode.
        Significantly reduces DB round-trips and API overhead.
        """
        # Self-healing: Reset any articles stuck in 'processing' for more than 1 hour
        from datetime import timedelta

        stuck_cutoff = timezone.now() - timedelta(hours=1)
        stuck_count = CAArticle.objects.filter(
            processing_status="processing", updated_at__lt=stuck_cutoff
        ).update(processing_status="pending")
        if stuck_count > 0:
            logger.info("stuck_articles_reset", count=stuck_count)

        pending_articles_qs = CAArticle.objects.filter(
            processing_status="pending"
        ).order_by("published_at")[:batch_size]

        # Convert to list to avoid sliced QuerySet issue for bulk_update and iterations
        pending_articles = list(pending_articles_qs)

        if not pending_articles:
            return 0

        article_ids = [a.id for a in pending_articles]
        logger.info("batch_processing_ca_articles_start", count=len(article_ids))

        # 1. Mark articles as processing immediately
        CAArticle.objects.filter(id__in=article_ids).update(
            processing_status="processing"
        )

        all_chunks_to_create: List[Dict[str, Any]] = []
        article_chunk_counts: Dict[Any, int] = (
            {}
        )  # track chunks per article for final status update

        # 2. Chunking Logic (CPU bound, fast local operation)
        for article in pending_articles:
            try:
                chunks_text = CAProcessorService._chunk_content(article.content)
                if not chunks_text and article.content and len(article.content) > 10:
                    chunks_text = [article.content.strip()]

                if not chunks_text:
                    article.processing_status = "failed"
                    article.processing_error = "No valid chunks generated"
                    continue

                # Keep metadata about chunks to link them back to the article
                article_chunk_counts[article.id] = len(chunks_text)
                for idx, text in enumerate(chunks_text):
                    all_chunks_to_create.append(
                        {
                            "article": article,
                            "text": text,
                            "index": idx,
                            "published_at": article.published_at,
                        }
                    )
            except Exception as e:
                logger.error(
                    "chunking_failed", article_id=str(article.id), error=str(e)
                )
                article.processing_status = "failed"
                article.processing_error = f"Chunking failed: {str(e)}"

        if not all_chunks_to_create:
            # Mark remaining "processing" articles as failed if no chunks produced
            CAArticle.objects.filter(
                id__in=article_ids, processing_status="processing"
            ).update(
                processing_status="failed", processing_error="No chunks to process"
            )
            return 0

        # 3. Batch Embedding (THE BIGGEST WIN - ONE API CALL)
        try:
            texts_to_embed = [c["text"] for c in all_chunks_to_create]
            logger.info("generating_embeddings_batch", total_chunks=len(texts_to_embed))
            vectors = EmbeddingService.generate_embeddings_batch(texts_to_embed)
        except Exception as e:
            logger.error("batch_embedding_failed", error=str(e))
            CAArticle.objects.filter(id__in=article_ids).update(
                processing_status="failed",
                processing_error=f"Embedding API failed: {str(e)}",
            )
            return 0

        # 4. Bulk DB Creation (Optimized for Mumbai Latency)
        try:
            from datetime import timedelta

            with transaction.atomic():
                # 4a. Create Chunks
                chunks_objects = [
                    CAChunk(
                        ca_article=c["article"],
                        chunk_text=c["text"],
                        chunk_index=c["index"],
                        source_type="dynamic",
                        published_at=c["published_at"],
                        expiry_date=c["published_at"] + timedelta(days=180),
                        quality_flag="medium",
                        confidence_score=0.7,
                    )
                    for c in all_chunks_to_create
                ]
                # bulk_create returns the objects with IDs set (on PostgreSQL)
                created_chunks = CAChunk.objects.bulk_create(chunks_objects)

                # 4b. Create Embeddings
                embedding_objects = [
                    Embedding(
                        content_type="ca_chunk",
                        content_id=chunk.id,
                        vector=vec,
                        model_name=EmbeddingService.MODEL_NAME,
                    )
                    for chunk, vec in zip(created_chunks, vectors)
                ]
                created_embeddings = Embedding.objects.bulk_create(embedding_objects)

                # 4c. Update Chunks with Embedding IDs (Linking)
                # Note: We need another bulk update or can stay as is if we don't strictly need the FK in CAChunk
                # (PostgreSQL allows us to do this because IDs are ready)
                for chunk, embedding in zip(created_chunks, created_embeddings):
                    chunk.embedding_id = embedding.id

                CAChunk.objects.bulk_update(created_chunks, fields=["embedding_id"])

                # 5. Final Status Update
                for article in pending_articles:
                    if article.id in article_chunk_counts:
                        article.processing_status = "completed"
                        article.chunk_count = article_chunk_counts[article.id]
                        article.processed_at = timezone.now()
                    # If an article failed chunking, its status and error are already set on the object
                    # We need to ensure these are also updated in the bulk_update
                    elif article.processing_status == "processing":
                        # This case should ideally not happen if the logic above is correct,
                        # but as a safeguard, mark as failed if still 'processing' without chunks
                        article.processing_status = "failed"
                        article.processing_error = "No chunks generated for article"

                CAArticle.objects.bulk_update(
                    pending_articles,
                    fields=[
                        "processing_status",
                        "chunk_count",
                        "processed_at",
                        "processing_error",
                    ],
                )

            logger.info(
                "batch_processing_ca_completed",
                articles=len(pending_articles),
                chunks=len(created_chunks),
            )
            return len(pending_articles)

        except Exception as e:
            logger.error("bulk_db_save_failed", error=str(e))
            CAArticle.objects.filter(id__in=article_ids).update(
                processing_status="failed",
                processing_error=f"Bulk DB save failed: {str(e)}",
            )
            return 0
