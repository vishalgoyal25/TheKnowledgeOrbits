"""
AI-Assisted Chunk-Topic Mapping Service

Uses embedding similarity to suggest relevant chunks for topics.
"""

from typing import Any, Dict, List, cast

import sentry_sdk
import structlog

logger = structlog.get_logger(__name__)


class MappingService:
    """Service for AI-assisted chunk-topic mapping."""

    SIMILARITY_THRESHOLD = 0.40  # Minimum score to consider relevant
    MAX_SUGGESTIONS = 30  # Max chunks to suggest

    @classmethod
    def auto_suggest_chunks(cls, topic_id: str, limit: int = 20) -> List[Dict]:  # type: ignore
        """
        Auto-suggest relevant chunks for a topic using AI.

        Uses embedding similarity between topic description/keywords
        and chunk embeddings.

        Args:
            topic_id: UUID of topic
            limit: Maximum suggestions to return

        Returns:
            List of dicts with chunk info and relevance scores
        """
        from engines.content.models import Chunk, Embedding
        from engines.content.services.embedding_service import EmbeddingService
        from engines.knowledge.models import ChunkTopicMap, Topic

        try:
            # Get topic
            topic = Topic.objects.get(id=topic_id)

            logger.info(
                "auto_suggest_started", topic_id=topic_id, topic_name=topic.name
            )

            # Step 1: Generate topic embedding
            topic_text = cls._build_topic_text(topic)
            topic_embedding = EmbeddingService.generate_embedding(topic_text)

            if not topic_embedding or len(topic_embedding) == 0:
                logger.error("topic_embedding_failed", topic_id=topic_id)
                return []

            logger.info(
                "topic_embedding_generated",
                topic_id=topic_id,
                embedding_dim=len(topic_embedding),
            )

            # Step 2: Get already mapped chunks (exclude from suggestions)
            already_mapped = set(
                ChunkTopicMap.objects.filter(topic=topic).values_list(
                    "chunk_id", flat=True
                )
            )

            logger.info(
                "already_mapped_chunks", topic_id=topic_id, count=len(already_mapped)
            )

            # Step 3: Find similar chunks using embedding similarity
            all_embeddings = Embedding.objects.filter(content_type="chunk").exclude(
                content_id__in=already_mapped
            )

            suggestions = []

            for embedding in all_embeddings:
                try:
                    # Calculate cosine similarity
                    similarity = cls._cosine_similarity(
                        topic_embedding, embedding.vector
                    )

                    # Filter by threshold
                    if similarity >= cls.SIMILARITY_THRESHOLD:
                        chunk = Chunk.objects.get(id=embedding.content_id)

                        suggestions.append(
                            {
                                "chunk_id": str(chunk.id),
                                "chunk_text": chunk.chunk_text,
                                "chunk_index": chunk.chunk_index,
                                "page_number": chunk.page_number,
                                "chapter_name": chunk.chapter_name,
                                "document_id": str(chunk.document_id),
                                "document_title": chunk.document.title,
                                "relevance_score": round(similarity, 3),
                                "quality_flag": chunk.quality_flag,
                            }
                        )

                except Exception as e:
                    sentry_sdk.capture_exception(e)
                    logger.warning(
                        "chunk_similarity_failed",
                        embedding_id=str(embedding.id),
                        error=str(e),
                    )
                    continue

            # Step 4: Sort by relevance and limit
            suggestions.sort(
                key=lambda x: cast(float, x["relevance_score"]), reverse=True
            )
            suggestions = suggestions[: min(limit, cls.MAX_SUGGESTIONS)]

            logger.info(
                "auto_suggest_completed",
                topic_id=topic_id,
                total_candidates=all_embeddings.count(),
                suggestions_count=len(suggestions),
                top_score=suggestions[0]["relevance_score"] if suggestions else 0,
            )

            return suggestions

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error("auto_suggest_failed", topic_id=topic_id, error=str(e))
            raise

    @classmethod
    def approve_mappings(
        cls, topic_id: str, chunk_ids: List[str], user_id: str, priority: int = 1
    ) -> Dict:  # type: ignore
        """
        Create approved chunk-topic mappings.

        Args:
            topic_id: UUID of topic
            chunk_ids: List of chunk UUIDs to map
            user_id: User who approved (for audit)
            priority: Priority level (1=basic, 2=intermediate, 3=advanced)

        Returns:
            Result dict with created count
        """
        from engines.auth.models import User
        from engines.content.models import Chunk
        from engines.knowledge.models import ChunkTopicMap, Topic

        try:
            topic = Topic.objects.get(id=topic_id)
            user = User.objects.get(id=user_id)

            logger.info(
                "approve_mappings_started",
                topic_id=topic_id,
                chunk_count=len(chunk_ids),
                user_id=user_id,
            )

            created_count = 0
            skipped_count = 0

            for chunk_id in chunk_ids:
                try:
                    chunk = Chunk.objects.get(id=chunk_id)

                    # Check if mapping already exists
                    existing = ChunkTopicMap.objects.filter(
                        chunk=chunk, topic=topic
                    ).first()

                    if existing:
                        logger.info(
                            "mapping_already_exists",
                            chunk_id=chunk_id,
                            topic_id=topic_id,
                        )
                        skipped_count += 1
                        continue

                    # Calculate relevance score
                    relevance = cls._calculate_relevance(chunk, topic)

                    # Create mapping
                    ChunkTopicMap.objects.create(
                        chunk=chunk,
                        topic=topic,
                        relevance_score=relevance,
                        priority=priority,
                        auto_mapped=True,
                        approved_by=user,
                    )

                    created_count += 1

                    logger.info(
                        "mapping_created",
                        chunk_id=chunk_id,
                        topic_id=topic_id,
                        relevance=relevance,
                    )

                except Chunk.DoesNotExist:
                    logger.warning("chunk_not_found", chunk_id=chunk_id)
                    skipped_count += 1
                    continue

            logger.info(
                "approve_mappings_completed",
                topic_id=topic_id,
                created=created_count,
                skipped=skipped_count,
            )

            return {
                "topic_id": topic_id,
                "created": created_count,
                "skipped": skipped_count,
                "total_mappings": topic.chunk_mappings.count(),
            }

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error("approve_mappings_failed", topic_id=topic_id, error=str(e))
            raise

    @classmethod
    def _build_topic_text(cls, topic: Any) -> str:
        """
        Build comprehensive text representation of topic for embedding.

        Combines: name + description + keywords
        """
        parts = [topic.name]

        if topic.description:
            parts.append(topic.description)

        if topic.keywords:
            parts.append(" ".join(topic.keywords))

        return " ".join(parts)

    @classmethod
    def _cosine_similarity(cls, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Returns:
            Similarity score (0.0 to 1.0)
        """
        import math

        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have same dimensions")

        # Dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))

        # Magnitudes
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        # Cosine similarity
        similarity = dot_product / (magnitude1 * magnitude2)

        # Clamp to [0, 1]
        return max(0.0, min(1.0, similarity))

    @classmethod
    def _calculate_relevance(cls, chunk: Any, topic: Any) -> float:
        """
        Calculate relevance score for chunk-topic pair.

        Uses embedding similarity if available, otherwise returns default.
        """
        try:
            from engines.content.models import Embedding
            from engines.content.services.embedding_service import EmbeddingService

            # Get chunk embedding
            chunk_emb = Embedding.objects.filter(
                content_type="chunk", content_id=str(chunk.id)
            ).first()

            if not chunk_emb:
                return 0.8  # Default score

            # Generate topic embedding
            topic_text = cls._build_topic_text(topic)
            topic_embedding = EmbeddingService.generate_embedding(topic_text)

            # Calculate similarity
            similarity = cls._cosine_similarity(topic_embedding, chunk_emb.vector)

            return similarity

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.warning(
                "relevance_calculation_failed",
                chunk_id=str(chunk.id),
                topic_id=str(topic.id),
                error=str(e),
            )
            return 0.8  # Default score on error
