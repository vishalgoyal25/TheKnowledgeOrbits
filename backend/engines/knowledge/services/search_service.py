"""
Unified Search Service using pgvector
"""

import sentry_sdk
from django.db.models import Q
from typing import List, Dict, Any
import structlog
from pgvector.django import CosineDistance
from engines.content.services.embedding_service import EmbeddingService
from engines.content.models import Chunk, Embedding
from engines.knowledge.models import Topic
from engines.current_affairs.models import CAArticle
from engines.article_generation.models import Article as GeneratedArticle

logger = structlog.get_logger(__name__)


class SearchService:
    @classmethod
    def semantic_search(cls, query: str, limit: int = 10, user: Any = None) -> List[Dict]:  # type: ignore
        """
        Perform semantic search across all content types.
        """
        try:
            results = []

            # 1. Generate query embedding
            try:
                query_vector = EmbeddingService.generate_embedding(query)
            except Exception as e:
                sentry_sdk.capture_exception(e)
                logger.error("embedding_generation_failed", error=str(e), query=query)
                query_vector = None

            # --- STRATEGY A1: Vector Search for Chunks (Core Content) ---
            if query_vector:
                try:
                    # Find closest vectors in Embedding table using cosine distance
                    # We now search for chunks AND articles AND ca_chunks
                    # Filter by distance < 0.60 to remove noise (0=identical, 1=orthogonal)
                    embeddings = (
                        Embedding.objects.annotate(
                            distance=CosineDistance("vector", query_vector)
                        )
                        .order_by("distance")
                        .filter(
                            content_type__in=["chunk", "article", "ca_chunk"],
                            distance__lt=0.60,
                        )[:limit]
                    )

                    for emb in embeddings:
                        # Case A: Static Chunk
                        if emb.content_type == "chunk":
                            try:
                                chunk = Chunk.objects.select_related("document").get(
                                    id=emb.content_id
                                )
                                results.append(
                                    {
                                        "id": str(chunk.id),
                                        "type": "article",
                                        "title": chunk.document.title,
                                        "snippet": chunk.chunk_text[:250] + "...",
                                        "url": f"/articles/{chunk.document.id}?chunk={chunk.chunk_index}&type=document&start_index={chunk.chunk_index}",
                                        "metadata": {
                                            "source": chunk.document.source_type,
                                            "chapter": chunk.chapter_name or "General",
                                        },
                                    }
                                )
                            except Chunk.DoesNotExist:
                                continue

                        # Case B: AI Generated Article
                        elif emb.content_type == "article":
                            try:
                                art = GeneratedArticle.objects.select_related(
                                    "topic"
                                ).get(id=emb.content_id)
                                results.insert(
                                    0,
                                    {  # Boost to top
                                        "id": str(art.id),
                                        "type": "article",
                                        "title": art.title,
                                        "snippet": (
                                            art.summary[:200] + "..."
                                            if art.summary
                                            else "AI Generated Article"
                                        ),
                                        "url": f"/articles/{art.id}",
                                        "metadata": {
                                            "source": "AI Generated",
                                            "topic": art.topic.name,
                                            "date": art.created_at.strftime("%Y-%m-%d"),
                                        },
                                    },
                                )
                            except GeneratedArticle.DoesNotExist:
                                continue

                        # Case C: CA Chunk (Current Affairs) - Link to parent article
                        # Note: We need to resolve CAChunk -> CAArticle
                        elif emb.content_type == "ca_chunk":
                            # We need to import CAChunk here to avoid circular imports if possible, or use raw query
                            from engines.current_affairs.models import CAChunk

                            try:
                                ca_chunk = CAChunk.objects.select_related(
                                    "ca_article", "ca_article__source"
                                ).get(id=emb.content_id)
                                # Deduplicate parent article if already in results ?
                                if not any(
                                    r["id"] == str(ca_chunk.ca_article.id)
                                    and r["type"] == "current_affair"
                                    for r in results
                                ):
                                    results.append(
                                        {
                                            "id": str(
                                                ca_chunk.ca_article.id
                                            ),  # valid GUID
                                            "type": "current_affair",
                                            "title": ca_chunk.ca_article.title,
                                            "snippet": ca_chunk.chunk_text[:200]
                                            + "...",
                                            "url": f"/current-affairs/{ca_chunk.ca_article.id}",
                                            "metadata": {
                                                "source": ca_chunk.ca_article.source.name,
                                                "date": ca_chunk.published_at.strftime(
                                                    "%Y-%m-%d"
                                                ),
                                            },
                                        }
                                    )
                            except (
                                Exception
                            ) as e:  # CAChunk might not exist or import error
                                logger.debug(
                                    f"CAChunk lookup failed for search result: {str(e)}"
                                )  # nosec: B112
                                continue

                except Exception as e:
                    sentry_sdk.capture_exception(e)
                    # If vector search fails (e.g. pgvector not installed/configured), log and continue to keyword search
                    logger.warning("vector_search_failed", error=str(e))

            # --- STRATEGY A2: Explicit Keyword Fallback for Chunks ---
            # If vectors are missing or user wants exact keyword match, we MUST search text too.
            # This ensures "Constitution" finds articles about Constitution even if vector distance is weird.
            keyword_chunks = Chunk.objects.filter(
                Q(chunk_text__icontains=query) | Q(document__title__icontains=query)
            ).select_related("document")[:5]

            for chunk in keyword_chunks:
                # Deduplicate: Don't add if already found by vector search
                if not any(r["id"] == str(chunk.id) for r in results):
                    results.append(
                        {
                            "id": str(chunk.id),
                            "type": "article",
                            "title": chunk.document.title,
                            "snippet": chunk.chunk_text[:250] + "...",
                            "url": f"/articles/{chunk.document.id}?chunk={chunk.chunk_index}&type=document",
                            "metadata": {
                                "source": chunk.document.source_type,
                                "chapter": chunk.chapter_name or "General",
                            },
                        }
                    )

            # --- STRATEGY B: Semantic Keyword Search for Topics ---
            # Even if we don't have topic embeddings yet, we search their descriptions
            topics = Topic.objects.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(keywords__contains=[query])
            )[:5]

            for topic in topics:
                results.append(
                    {
                        "id": str(topic.id),
                        "type": "topic",
                        "title": topic.name,
                        "snippet": (
                            topic.description[:150] + "..."
                            if topic.description
                            else "Explore this topic in depth."
                        ),
                        "url": f"/topics/{topic.id}",
                        "metadata": {
                            "subject": (
                                topic.subject.name if topic.subject else "General"
                            ),
                            "level": topic.difficulty_level,
                        },
                    }
                )

            # --- STRATEGY C: Current Affairs Search ---
            current_affairs = CAArticle.objects.select_related("source").filter(
                Q(title__icontains=query)
                | Q(summary__icontains=query)
                | Q(content__icontains=query)
            )[:5]

            for ca in current_affairs:
                # Deduplicate if already found by vector search
                if not any(
                    r["id"] == str(ca.id) and r["type"] == "current_affair"
                    for r in results
                ):
                    results.append(
                        {
                            "id": str(ca.id),
                            "type": "current_affair",
                            "title": ca.title,
                            "snippet": (
                                ca.summary[:200] + "..."
                                if ca.summary
                                else "Latest update on this topic."
                            ),
                            "url": f"/current-affairs/{ca.id}",
                            "metadata": {
                                "source": ca.source.name,
                                "date": (
                                    ca.published_at.strftime("%Y-%m-%d")
                                    if ca.published_at
                                    else "Recent"
                                ),
                            },
                        }
                    )

            # --- STRATEGY D: AI Generated Articles Search ---
            # Search actual generated articles first
            generated_articles = (
                GeneratedArticle.objects.filter(
                    Q(title__icontains=query)
                    | Q(topic__name__icontains=query)
                    | Q(content__icontains=query)  # Search in full article text
                )
                .filter(is_published=True)
                .select_related("topic")[:5]
            )

            for art in generated_articles:
                # Deduplicate if already found by vector search
                if not any(r["id"] == str(art.id) for r in results):
                    results.insert(
                        0,
                        {  # Insert at top
                            "id": str(art.id),
                            "type": "article",  # Keep 'article' type so it opens normally (AI Article)
                            "title": art.title,
                            "snippet": (
                                art.summary[:200] + "..."
                                if art.summary
                                else "AI Generated Article"
                            ),
                            "url": f"/articles/{art.id}",
                            "metadata": {
                                "source": "AI Generated",
                                "topic": art.topic.name,
                                "date": art.created_at.strftime("%Y-%m-%d"),
                            },
                        },
                    )

            return results

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error("semantic_search_failed", error=str(e))
            return []
