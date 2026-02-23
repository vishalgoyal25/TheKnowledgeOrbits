import sentry_sdk

"""
Topic Linker Service

Auto-links CA chunks to syllabus topics using semantic similarity
"""

from typing import Any, Dict, List, cast

import numpy as np
import structlog
from sentence_transformers import SentenceTransformer

from engines.content.models import Embedding
from engines.knowledge.models import Topic

from ..models import CAChunk, CATopicLink

logger = structlog.get_logger(__name__)

# Initialize model for fallback topic embedding generation
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


class TopicLinkerService:
    """Auto-link CA chunks to topics"""

    SIMILARITY_THRESHOLD = 0.35  # Lowered threshold to catch broader matches
    MAX_LINKS_PER_CHUNK = 3  # Max topics per chunk

    @staticmethod
    def link_chunk_to_topics(ca_chunk: CAChunk) -> int:
        """
        Link a single CA chunk to relevant topics

        Returns:
            int: Number of topics linked
        """
        chunks_id_str = str(ca_chunk.id)
        logger.info("linking_ca_chunk_to_topics", chunk_id=chunks_id_str)

        try:
            # Get CA chunk embedding
            if not ca_chunk.embedding_id:
                logger.warning(
                    "CA chunk has no embedding", extra={"chunk_id": chunks_id_str}
                )
                # Attempt to fix missing embedding if content exists?
                # No, that's processor's job.
                return 0

            try:
                ca_embedding = Embedding.objects.get(id=ca_chunk.embedding_id)
            except Embedding.DoesNotExist:
                logger.error(
                    f"Embedding {ca_chunk.embedding_id} not found for chunk {chunks_id_str}"
                )
                return 0

            ca_vector = np.array(ca_embedding.vector)

            # Get all topic embeddings (hybrid approach: chunk-based + description-based)
            topic_embeddings = TopicLinkerService._get_topic_embeddings()

            if not topic_embeddings:
                logger.warning("no_topic_embeddings_available")
                return 0

            # Calculate similarities
            similarities: List[Dict[str, Any]] = []
            max_sim = 0.0
            best_topic_id = None

            for topic_id, topic_vector in topic_embeddings.items():
                similarity = TopicLinkerService._cosine_similarity(
                    ca_vector, topic_vector
                )

                if similarity > max_sim:
                    max_sim = similarity
                    best_topic_id = topic_id

                if similarity >= TopicLinkerService.SIMILARITY_THRESHOLD:
                    similarities.append(
                        {"topic_id": topic_id, "similarity": float(similarity)}
                    )

            # Sort by similarity (descending)
            similarities.sort(key=lambda x: cast(float, x["similarity"]), reverse=True)

            # Take top N
            top_similarities = similarities[: TopicLinkerService.MAX_LINKS_PER_CHUNK]

            # Create links
            links_created = 0
            current_topic_ids = []

            for sim in top_similarities:
                topic = Topic.objects.get(id=str(sim["topic_id"]))
                current_topic_ids.append(topic.id)

                # Create or update link
                link, created = CATopicLink.objects.update_or_create(
                    ca_chunk=ca_chunk,
                    topic=topic,
                    defaults={
                        "relevance_score": float(cast(float, sim["similarity"])),
                        "link_method": "auto",
                    },
                )

                if created:
                    links_created += 1

            if links_created == 0:
                logger.debug(
                    "no_strong_topic_links_found",
                    chunk_id=chunks_id_str,
                    max_similarity=max_sim,
                    best_topic_id=best_topic_id,
                    threshold=TopicLinkerService.SIMILARITY_THRESHOLD,
                )

            logger.info(
                "linked_ca_chunk_to_topics",
                links_created=links_created,
                chunk_id=chunks_id_str,
                topics=[str(tid) for tid in current_topic_ids],
                max_similarity=max_sim,
            )

            return links_created

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(
                "failed_to_link_ca_chunk",
                error=str(e),
                chunk_id=str(ca_chunk.id),
                exc_info=True,
            )
            return 0

    @staticmethod
    def _get_topic_embeddings() -> Dict[str, np.ndarray]:  # type: ignore
        """
        Get representative embeddings for each topic.

        Strategy:
        1. Try to get average of mapped static chunks (Content <> Knowledge).
        2. If NO chunks are mapped (Cold Start), generate embedding from Topic Name + Description.
        """
        from engines.knowledge.models import ChunkTopicMap

        topic_embeddings = {}

        # Get all active topics
        topics = Topic.objects.filter(is_active=True)

        # Optimization: Generate all descriptions first to batch encode?
        # For simplicity/speed of implementation now, we loop.

        for topic in topics:
            # 1. Try Chunk-Based Embedding
            chunk_ids = ChunkTopicMap.objects.filter(topic=topic).values_list(
                "chunk_id", flat=True
            )[:10]

            avg_vector = None

            if chunk_ids:
                embeddings = Embedding.objects.filter(
                    content_type="chunk", content_id__in=[str(cid) for cid in chunk_ids]
                )

                if embeddings.exists():
                    vectors = [np.array(emb.vector) for emb in embeddings]
                    # vectors is list of numpy arrays. mean over axis 0.
                    # Ensure vectors are not empty/malformed
                    if vectors:
                        avg_vector = np.mean(vectors, axis=0)

            # 2. Fallback: Description-Based Embedding (Cold Start Support)
            if avg_vector is None:
                # Construct rich text representation of the topic
                topic_text = f"{topic.name}. {topic.description}"
                if topic.keywords:
                    topic_text += f" Keywords: {', '.join(topic.keywords)}"

                # Generate embedding on the fly
                # Note: This is slower but runs only once per topic per batch usually
                # We should cache this in future, but fine for now.
                avg_vector = embedding_model.encode(topic_text)

            topic_embeddings[str(topic.id)] = np.array(avg_vector)

        logger.info(f"Loaded {len(topic_embeddings)} topic embeddings")

        return cast(Dict[str, np.ndarray], topic_embeddings)  # type: ignore

    @staticmethod
    def _cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:  # type: ignore
        """Calculate cosine similarity between two vectors"""
        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)

        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0

        return dot_product / (norm_v1 * norm_v2)  # type: ignore

    @staticmethod
    def link_unlinked_chunks(batch_size: int = 20) -> int:
        """
        Link CA chunks that have no topic links yet

        Returns:
            int: Number of links created
        """
        # Get unlinked chunks
        unlinked_chunks = CAChunk.objects.filter(
            topic_links__isnull=True, is_expired=False
        ).order_by("-published_at")[:batch_size]

        processed_chunks_count = 0
        total_links_created = 0

        logger.info("bulk_linking_unlinked_chunks", count=unlinked_chunks.count())

        for chunk in unlinked_chunks:
            links = TopicLinkerService.link_chunk_to_topics(chunk)
            processed_chunks_count += 1
            total_links_created += links

        logger.info(
            f"Processed {processed_chunks_count} chunks, Created {total_links_created} links"
        )

        # Return total links created to match the management command's expectation of "activity"
        return total_links_created
