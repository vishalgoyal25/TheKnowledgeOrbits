import sentry_sdk  # type: ignore

"""
Topic Linker Service

Auto-links CA chunks to syllabus topics using semantic similarity
"""

from typing import Any, Dict, List, Optional, cast

import numpy as np  # type: ignore
import structlog  # type: ignore

from engines.content.models import Embedding  # type: ignore
from engines.knowledge.models import ChunkTopicMap, Topic  # type: ignore

from ..models import CAChunk, CATopicLink  # type: ignore

from collections import defaultdict

logger = structlog.get_logger(__name__)

_embedding_model = None


def get_embedding_model():
    """Lazy load SentenceTransformer so it doesn't boot during Django startup."""
    global _embedding_model
    if _embedding_model is None:
        logger.info("lazy_loading_sentence_transformer")
        from sentence_transformers import SentenceTransformer  # type: ignore

        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


class TopicLinkerService:
    """Auto-link CA chunks to topics"""

    SIMILARITY_THRESHOLD = 0.35  # Lowered threshold to catch broader matches
    MAX_LINKS_PER_CHUNK = 3  # Max topics per chunk

    @staticmethod
    def link_chunk_to_topics(
        ca_chunk: CAChunk, topic_embeddings: Optional[Dict[str, np.ndarray]] = None
    ) -> int:
        """
        Link a single CA chunk to relevant topics.
        Optionally accepts pre-calculated topic_embeddings to avoid redundant work in batches.

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
                return 0

            try:
                ca_embedding = Embedding.objects.get(id=ca_chunk.embedding_id)
            except Embedding.DoesNotExist:
                logger.error(
                    f"Embedding {ca_chunk.embedding_id} not found for chunk {chunks_id_str}"
                )
                return 0

            ca_vector = np.array(ca_embedding.vector)

            # Get all topic embeddings (hybrid approach)
            # Use provided embeddings if in a batch, otherwise fetch fresh
            if topic_embeddings is None:
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

            # Take top N (Max 3 links per chunk)
            top_similarities = []
            for i in range(len(similarities)):
                if i >= 3:  # Hard limit for safety and linter clarity
                    break
                top_similarities.append(similarities[i])

            # Create links
            linked_ids = set()
            current_topic_ids = []

            for sim in top_similarities:
                topic = Topic.objects.get(id=str(sim["topic_id"]))
                current_topic_ids.append(topic.id)

                # Create or update link
                _, created = CATopicLink.objects.update_or_create(
                    ca_chunk=ca_chunk,
                    topic=topic,
                    defaults={
                        "relevance_score": float(cast(float, sim["similarity"])),
                        "link_method": "auto",
                    },
                )

                if created:
                    linked_ids.add(str(topic.id))

            final_count = len(linked_ids)

            if final_count == 0:
                logger.debug(
                    "no_strong_topic_links_found",
                    chunk_id=chunks_id_str,
                    max_similarity=max_sim,
                    best_topic_id=best_topic_id,
                    threshold=TopicLinkerService.SIMILARITY_THRESHOLD,
                )

            logger.info(
                "linked_ca_chunk_to_topics",
                links_created=final_count,
                chunk_id=chunks_id_str,
                topics=[str(tid) for tid in current_topic_ids],
                max_similarity=max_sim,
            )

            return int(final_count)

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
        Get representative embeddings for each topic using an optimized bulk strategy.

        """
        topic_embeddings = {}

        # 1. Fetch all active topics
        topics = list(Topic.objects.filter(is_active=True))
        if not topics:
            return {}

        # 2. Optimized Bulk Query for Mappings
        # Get all chunk IDs mapped to these topics in ONE query
        topic_ids = [str(t.id) for t in topics]
        mappings = ChunkTopicMap.objects.filter(topic_id__in=topic_ids).values(
            "topic_id", "chunk_id"
        )

        topic_to_chunk_ids = defaultdict(list)
        for m in mappings:
            topic_to_chunk_ids[str(m["topic_id"])].append(str(m["chunk_id"]))

        # 3. Optimized Bulk Query for Embeddings
        # Collect ALL unique chunk IDs that we need vectors for
        all_chunk_ids = set()
        for cids in topic_to_chunk_ids.values():
            all_chunk_ids.update(cids)

        # Fetch all relevant embeddings in ONE query
        embeddings_qs = Embedding.objects.filter(
            content_type="chunk", content_id__in=list(all_chunk_ids)
        )

        chunk_id_to_vector = {
            str(e.content_id): np.array(e.vector) for e in embeddings_qs
        }

        # 4. Group and Average Vectors
        topics_needing_encoding = []
        for topic in topics:
            tid = str(topic.id)
            cids = topic_to_chunk_ids.get(tid, [])
            vectors = [
                chunk_id_to_vector[cid] for cid in cids if cid in chunk_id_to_vector
            ]

            if vectors:
                topic_embeddings[tid] = np.mean(vectors, axis=0)
            else:
                topics_needing_encoding.append(topic)

        # 5. Batch Encode topics without existing chunk mappings (Cold Start)
        if topics_needing_encoding:
            logger.info(
                f"Batch encoding {len(topics_needing_encoding)} Cold Start topics"
            )

            # Form texts for batch processing (faster than one by one)
            encoding_texts = []
            for topic in topics_needing_encoding:
                text = f"{topic.name}. {topic.description}"
                if topic.keywords:
                    text += f" Keywords: {', '.join(topic.keywords)}"
                encoding_texts.append(text)

            # Bulk encode using the model
            model = get_embedding_model()
            vectors = model.encode(encoding_texts, convert_to_numpy=True)

            for i, topic in enumerate(topics_needing_encoding):
                topic_embeddings[str(topic.id)] = vectors[i]

        logger.info(f"Successfully loaded {len(topic_embeddings)} topic embeddings")
        return topic_embeddings

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

        # CRITICAL OPTIMIZATION: Load all topic embeddings ONCE for the entire batch
        topic_embeddings = TopicLinkerService._get_topic_embeddings()

        for chunk in unlinked_chunks:
            # Pass the pre-calculated embeddings to avoid redundant re-calculation
            links = TopicLinkerService.link_chunk_to_topics(
                chunk, topic_embeddings=topic_embeddings
            )
            processed_chunks_count += 1
            total_links_created += links

        logger.info(
            f"Processed {processed_chunks_count} chunks, Created {total_links_created} links"
        )

        # Return total links created to match the management command's expectation of "activity"
        return total_links_created
