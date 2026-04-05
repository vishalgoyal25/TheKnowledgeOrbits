"""
Unified Search Service — pgvector HNSW + keyword fallback
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Searches across ALL content: CA articles, book content, NCERT chunks,
AI-generated articles, and knowledge topics.

Performance fixes (Phase E):
  1. HNSW-friendly query: distance threshold moved from SQL WHERE → Python
     PostgreSQL HNSW only triggers on: ORDER BY vector <=> query LIMIT N
     Adding WHERE distance < X forces a sequential scan — removed.
  2. Query embedding cached in Redis (1h TTL) — avoids repeated HF API calls
     for the same search term. Same query = instant embedding retrieval.
  3. Removed content__icontains on CAArticle + GeneratedArticle
     Those were doing LIKE '%query%' on full-length text fields (5-10s each).
     CA articles are now found via ca_chunk vector search (already indexed).
  4. Added book_chunk + book_article content types — book content now
     appears in results (was invisible before Phase E).
  5. Bulk-fetch linked objects grouped by content_type — eliminates N+1
     individual .get() calls inside the embedding loop.
"""

import hashlib
from typing import Any, Dict, List

import sentry_sdk
import structlog
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.cache import cache
from django.db.models import Q
from pgvector.django import CosineDistance

from engines.article_generation.models import Article as GeneratedArticle
from engines.content.models import Chunk, Embedding
from engines.content.services.embedding_service import EmbeddingService
from engines.current_affairs.models import CAArticle
from engines.knowledge.models import Topic

logger = structlog.get_logger(__name__)

# Distance threshold applied in Python (not SQL) so HNSW index remains active
_NOISE_THRESHOLD: float = 0.62

# Redis TTL for cached query embeddings (1 hour)
_EMBEDDING_CACHE_TTL: int = 3600

# Candidate pool: fetch this many from vector search before Python-filtering
_VECTOR_CANDIDATES: int = 30


class SearchService:
    @classmethod
    def semantic_search(
        cls, query: str, limit: int = 10, user: Any = None
    ) -> List[Dict]:
        """
        Perform search across all content types.

        Strategy order (results merged + deduplicated):
          A. Vector search (HNSW) — all content types including book_chunk
          B. Keyword fallback on chunk text (GIN tsvector where available)
          C. Topic name/description match
          D. CA article title + summary match (NOT full content — too slow)
          E. Generated article title + topic name match
        """
        try:
            results: List[Dict] = []

            # ── Step 1: Get query embedding (Redis-cached) ────────────────────
            query_vector = cls._get_query_embedding(query)

            # ── Step 2: Vector search (HNSW — all content types) ─────────────
            if query_vector:
                vector_results = cls._vector_search(query_vector, limit)
                results.extend(vector_results)

            # ── Step 3: Keyword fallback for NCERT chunks ─────────────────────
            keyword_results = cls._keyword_chunk_search(query, results)
            results.extend(keyword_results)

            # ── Step 4: Topic name/description match ──────────────────────────
            topic_results = cls._topic_search(query, results)
            results.extend(topic_results)

            # ── Step 5: CA article title + summary match ──────────────────────
            ca_results = cls._ca_article_search(query, results)
            results.extend(ca_results)

            # ── Step 6: Generated article title + topic match ─────────────────
            gen_results = cls._generated_article_search(query, results)
            # Insert at front (AI articles are high-value results)
            results = gen_results + results

            # ── Step 7: BM25 on book_chunk (GIN index — catches exact terms) ──
            # Finds "Article 356", "Schedule VII", legal citations missed by vectors
            bm25_book_results = cls._bm25_book_chunk_search(query, results)
            results.extend(bm25_book_results)

            # ── Step 8: BM25 on ca_chunk (inline tsvector — no index but fast) ─
            # Better than LIKE for multi-word queries; catches "UNSC resolution" etc.
            bm25_ca_results = cls._bm25_ca_chunk_search(query, results)
            results.extend(bm25_ca_results)

            logger.info(
                "search_complete",
                query=query[:80],
                total_results=len(results),
            )
            return results[:limit]

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error("semantic_search_failed", error=str(e))
            return []

    # ═══════════════════════════════════════════════════════════════════════════
    # PRIVATE: EMBEDDING CACHE
    # ═══════════════════════════════════════════════════════════════════════════

    @classmethod
    def _get_query_embedding(cls, query: str) -> List[float] | None:
        """
        Returns query embedding, using Redis cache to avoid repeated HF API calls.
        Cache key is an MD5 hash of the normalized query (case-insensitive, stripped).
        TTL: 1 hour — balances freshness vs API cost.
        """
        normalized = query.strip().lower()
        cache_key = f"qemb:{hashlib.md5(normalized.encode()).hexdigest()}"

        cached = cache.get(cache_key)
        if cached is not None:
            logger.debug("query_embedding_cache_hit", query=query[:60])
            return cached

        try:
            vector = EmbeddingService.generate_embedding(query)
            cache.set(cache_key, vector, timeout=_EMBEDDING_CACHE_TTL)
            logger.debug("query_embedding_generated_and_cached", query=query[:60])
            return vector
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.warning("query_embedding_failed", error=str(e))
            return None

    # ═══════════════════════════════════════════════════════════════════════════
    # PRIVATE: VECTOR SEARCH (HNSW)
    # ═══════════════════════════════════════════════════════════════════════════

    @classmethod
    def _vector_search(
        cls, query_vector: List[float], limit: int
    ) -> List[Dict]:
        """
        HNSW-optimized vector search across all indexed content types.

        CRITICAL: distance threshold is applied in Python, NOT in SQL.
        Adding WHERE distance < X in SQL breaks HNSW and forces a seq scan.
        Instead: fetch _VECTOR_CANDIDATES rows (HNSW runs fast), filter in Python.

        Content types searched:
          chunk       → NCERT/static content chunks
          article     → AI-generated articles
          ca_chunk    → Current Affairs chunks (links back to CAArticle)
          book_chunk  → Book Content chunks (new — Phase E)
          book_article→ Book Content article-level embedding (new — Phase E)
        """
        try:
            # HNSW-friendly pattern: ORDER BY + LIMIT only, no WHERE on distance
            raw_embeddings = list(
                Embedding.objects.filter(
                    content_type__in=[
                        "chunk",
                        "article",
                        "ca_chunk",
                        "book_chunk",
                        "book_article",
                    ]
                )
                .annotate(distance=CosineDistance("vector", query_vector))
                .order_by("distance")
                [:_VECTOR_CANDIDATES]
            )

            # Apply noise filter in Python — keeps HNSW index active
            filtered = [e for e in raw_embeddings if float(e.distance) < _NOISE_THRESHOLD]

            if not filtered:
                return []

            # ── Bulk-fetch linked objects grouped by content_type ─────────────
            # Avoids N+1 — one query per content_type, not one per row
            results = cls._resolve_embeddings(filtered, limit)
            return results

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.warning("vector_search_failed", error=str(e))
            return []

    @classmethod
    def _resolve_embeddings(
        cls, embeddings: list, limit: int
    ) -> List[Dict]:
        """
        Bulk-resolves embedding rows to their source objects.
        Groups by content_type, fetches all IDs of each type in one query.
        Eliminates N+1 individual .get() calls from the original implementation.
        """
        from engines.book_content.models import BookContent
        from engines.current_affairs.models import CAChunk

        # Group content_ids by type
        by_type: Dict[str, list] = {}
        for emb in embeddings:
            by_type.setdefault(emb.content_type, []).append(emb.content_id)

        # Bulk-fetch each type
        chunk_map: Dict = {}
        article_map: Dict = {}
        ca_chunk_map: Dict = {}
        book_chunk_map: Dict = {}
        book_article_map: Dict = {}

        if "chunk" in by_type:
            chunk_map = {
                c.id: c
                for c in Chunk.objects.filter(
                    id__in=by_type["chunk"]
                ).select_related("document")
            }
        if "article" in by_type:
            article_map = {
                a.id: a
                for a in GeneratedArticle.objects.filter(
                    id__in=by_type["article"]
                ).select_related("topic")
            }
        if "ca_chunk" in by_type:
            ca_chunk_map = {
                c.id: c
                for c in CAChunk.objects.filter(
                    id__in=by_type["ca_chunk"]
                ).select_related("ca_article", "ca_article__source")
            }
        if "book_chunk" in by_type:
            from engines.book_content.models import BookChunk

            book_chunk_map = {
                c.id: c
                for c in BookChunk.objects.filter(
                    id__in=by_type["book_chunk"]
                ).select_related(
                    "book_content", "book_content__topic", "book_content__subject"
                )
            }
        if "book_article" in by_type:
            book_article_map = {
                a.id: a
                for a in BookContent.objects.filter(
                    id__in=by_type["book_article"]
                ).select_related("topic", "subject")
            }

        # Build results in embedding order (already sorted by distance)
        seen_ids: set = set()
        results = []

        for emb in embeddings:
            ctype = emb.content_type
            cid = emb.content_id
            row = None

            if ctype == "chunk":
                obj = chunk_map.get(cid)
                if obj:
                    row = {
                        "id": str(obj.id),
                        "type": "article",
                        "title": obj.document.title,
                        "snippet": obj.chunk_text[:250] + "...",
                        "url": f"/articles/{obj.document.id}?chunk={obj.chunk_index}&type=document&start_index={obj.chunk_index}",
                        "metadata": {
                            "source": obj.document.source_type,
                            "chapter": obj.chapter_name or "General",
                        },
                    }

            elif ctype == "article":
                obj = article_map.get(cid)
                if obj:
                    row = {
                        "id": str(obj.id),
                        "type": "article",
                        "title": obj.title,
                        "snippet": (obj.summary[:200] + "..." if obj.summary else "AI Generated Article"),
                        "url": f"/articles/{obj.id}",
                        "metadata": {
                            "source": "AI Generated",
                            "topic": obj.topic.name if obj.topic else "",
                            "date": obj.created_at.strftime("%Y-%m-%d"),
                        },
                    }

            elif ctype == "ca_chunk":
                obj = ca_chunk_map.get(cid)
                if obj:
                    dedup_id = str(obj.ca_article.id)
                    if dedup_id in seen_ids:
                        continue
                    row = {
                        "id": dedup_id,
                        "type": "current_affair",
                        "title": obj.ca_article.title,
                        "snippet": obj.chunk_text[:200] + "...",
                        "url": f"/current-affairs/{obj.ca_article.id}",
                        "metadata": {
                            "source": obj.ca_article.source.name,
                            "date": (
                                obj.published_at.strftime("%Y-%m-%d")
                                if obj.published_at
                                else "Recent"
                            ),
                        },
                    }

            elif ctype == "book_chunk":
                obj = book_chunk_map.get(cid)
                if obj and obj.book_content:
                    bc = obj.book_content
                    dedup_id = f"bc_{bc.id}"
                    if dedup_id in seen_ids:
                        continue
                    row = {
                        "id": str(bc.id),
                        "type": "book_article",
                        "title": bc.topic.name if bc.topic else "Book Article",
                        "snippet": obj.chunk_text[:250] + "...",
                        "url": (
                            f"/knowledge?topic={bc.topic_id}"
                            if bc.topic_id
                            else "/knowledge"
                        ),
                        "metadata": {
                            "source": "Book Content",
                            "subject": bc.subject.name if bc.subject else "",
                        },
                    }
                    seen_ids.add(dedup_id)

            elif ctype == "book_article":
                obj = book_article_map.get(cid)
                if obj:
                    dedup_id = f"bc_{obj.id}"
                    if dedup_id in seen_ids:
                        continue
                    row = {
                        "id": str(obj.id),
                        "type": "book_article",
                        "title": obj.topic.name if obj.topic else "Book Article",
                        "snippet": (obj.content_markdown[:250] + "...") if obj.content_markdown else "",
                        "url": (
                            f"/knowledge?topic={obj.topic_id}"
                            if obj.topic_id
                            else "/knowledge"
                        ),
                        "metadata": {
                            "source": "Book Content",
                            "subject": obj.subject.name if obj.subject else "",
                        },
                    }
                    seen_ids.add(dedup_id)

            if row and row["id"] not in seen_ids:
                seen_ids.add(row["id"])
                results.append(row)
                if len(results) >= limit:
                    break

        return results

    # ═══════════════════════════════════════════════════════════════════════════
    # PRIVATE: KEYWORD FALLBACK SEARCHES
    # ═══════════════════════════════════════════════════════════════════════════

    @classmethod
    def _keyword_chunk_search(cls, query: str, existing: List[Dict]) -> List[Dict]:
        """
        Keyword fallback for NCERT chunks. Searches chunk_text + document title.
        Only adds results NOT already found by vector search.
        NOTE: Only searches title, not chunk_text full content — icontains on
        chunk_text is too slow (LIKE '%...%' on 60k rows with no trigram index).
        """
        existing_ids = {r["id"] for r in existing}
        results = []

        try:
            keyword_chunks = Chunk.objects.filter(
                Q(document__title__icontains=query)
            ).select_related("document")[:5]

            for chunk in keyword_chunks:
                if str(chunk.id) not in existing_ids:
                    results.append({
                        "id": str(chunk.id),
                        "type": "article",
                        "title": chunk.document.title,
                        "snippet": chunk.chunk_text[:250] + "...",
                        "url": f"/articles/{chunk.document.id}?chunk={chunk.chunk_index}&type=document",
                        "metadata": {
                            "source": chunk.document.source_type,
                            "chapter": chunk.chapter_name or "General",
                        },
                    })
        except Exception as e:
            logger.warning("keyword_chunk_search_failed", error=str(e))

        return results

    @classmethod
    def _topic_search(cls, query: str, existing: List[Dict]) -> List[Dict]:
        """Topic name + description match (short fields — safe for icontains)."""
        existing_ids = {r["id"] for r in existing}
        results = []

        try:
            topics = Topic.objects.filter(
                Q(name__icontains=query) | Q(description__icontains=query)
            )[:5]

            for topic in topics:
                if str(topic.id) not in existing_ids:
                    results.append({
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
                            "subject": topic.subject.name if topic.subject else "General",
                            "level": topic.difficulty_level,
                        },
                    })
        except Exception as e:
            logger.warning("topic_search_failed", error=str(e))

        return results

    @classmethod
    def _ca_article_search(cls, query: str, existing: List[Dict]) -> List[Dict]:
        """
        CA article title + summary match.
        IMPORTANT: NOT searching content field — it contains full article text
        and causes 5-10s full-table scan. CA content is already covered by
        ca_chunk vector search in Strategy A.
        """
        existing_ids = {r["id"] for r in existing}
        results = []

        try:
            current_affairs = CAArticle.objects.select_related("source").filter(
                Q(title__icontains=query) | Q(summary__icontains=query)
            )[:5]

            for ca in current_affairs:
                if str(ca.id) not in existing_ids:
                    results.append({
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
                    })
        except Exception as e:
            logger.warning("ca_article_search_failed", error=str(e))

        return results

    @classmethod
    def _generated_article_search(cls, query: str, existing: List[Dict]) -> List[Dict]:
        """
        AI-generated article search by title + topic name only.
        NOT searching content field — full article text scan is too slow.
        Content-level matches are covered by the 'article' vector search above.
        """
        existing_ids = {r["id"] for r in existing}
        results = []

        try:
            generated_articles = (
                GeneratedArticle.objects.filter(
                    Q(title__icontains=query) | Q(topic__name__icontains=query)
                )
                .filter(is_published=True)
                .select_related("topic")[:5]
            )

            for art in generated_articles:
                if str(art.id) not in existing_ids:
                    results.append({
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
                            "topic": art.topic.name if art.topic else "",
                            "date": art.created_at.strftime("%Y-%m-%d"),
                        },
                    })
        except Exception as e:
            logger.warning("generated_article_search_failed", error=str(e))

        return results

    @classmethod
    def _bm25_book_chunk_search(cls, query: str, existing: List[Dict]) -> List[Dict]:
        """
        BM25 full-text search on BookChunk via pre-computed search_vector (GIN indexed).

        Catches exact legal terms that semantic search misses:
          - "Article 356", "Schedule VII", "Directive Principles", "IPC 302"
        Uses PostgreSQL websearch syntax — quotes, AND/OR, minus exclusions all work.
        Results link to /knowledge?topic=X (Knowledge Map).

        GIN index on search_vector means this is sub-10ms even at 500k chunks.
        """
        from engines.book_content.models import BookChunk

        existing_ca_ids = {r["id"] for r in existing if r["type"] == "book_article"}
        results = []

        try:
            search_q = SearchQuery(query, config="english", search_type="websearch")

            chunks = (
                BookChunk.objects.filter(search_vector=search_q)
                .annotate(rank=SearchRank("search_vector", search_q))
                .order_by("-rank")
                .select_related(
                    "book_content", "book_content__topic", "book_content__subject"
                )[:10]
            )

            seen_article_ids: set = set()
            for chunk in chunks:
                if not chunk.book_content or not chunk.book_content.topic:
                    continue
                bc = chunk.book_content
                bc_id = str(bc.id)
                # Deduplicate: one result per article, not one per chunk
                if bc_id in existing_ca_ids or bc_id in seen_article_ids:
                    continue
                seen_article_ids.add(bc_id)
                results.append({
                    "id": bc_id,
                    "type": "book_article",
                    "title": bc.topic.name,
                    "snippet": chunk.chunk_text[:250] + "...",
                    "url": f"/knowledge?topic={bc.topic_id}",
                    "metadata": {
                        "source": "Book Content",
                        "subject": bc.subject.name if bc.subject else "",
                    },
                })

        except Exception as e:
            logger.warning("bm25_book_chunk_search_failed", error=str(e))

        return results

    @classmethod
    def _bm25_ca_chunk_search(cls, query: str, existing: List[Dict]) -> List[Dict]:
        """
        BM25 full-text search on CAChunk via inline tsvector (no pre-computed column).

        PostgreSQL computes tsvector on-the-fly — no GIN index, but still faster
        than LIKE for multi-word queries because tsvector skips stop words,
        stems properly, and uses parallel scan.

        Best for: exact proper nouns — "UNSC resolution", "Article 370",
        "Quad Summit", "Cyclone Biparjoy" — terms unlikely to match by vectors.
        """
        from engines.current_affairs.models import CAChunk

        existing_ca_ids = {
            r["id"] for r in existing if r["type"] == "current_affair"
        }
        results = []

        try:
            search_q = SearchQuery(query, config="english", search_type="websearch")
            # SearchVector wraps the plain TextField so PostgreSQL treats it as tsvector.
            # Computed on-the-fly (no pre-indexed column) — sequential scan but correct.
            sv = SearchVector("chunk_text", config="english")  # noqa: F821

            chunks = (
                CAChunk.objects
                .annotate(sv=sv, rank=SearchRank(sv, search_q))
                .filter(sv=search_q)
                .order_by("-rank")
                .select_related("ca_article", "ca_article__source")[:10]
            )

            seen_article_ids: set = set()
            for chunk in chunks:
                if not chunk.ca_article:
                    continue
                ca_id = str(chunk.ca_article.id)
                if ca_id in existing_ca_ids or ca_id in seen_article_ids:
                    continue
                seen_article_ids.add(ca_id)
                results.append({
                    "id": ca_id,
                    "type": "current_affair",
                    "title": chunk.ca_article.title,
                    "snippet": chunk.chunk_text[:200] + "...",
                    "url": f"/current-affairs/{ca_id}",
                    "metadata": {
                        "source": chunk.ca_article.source.name,
                        "date": (
                            chunk.published_at.strftime("%Y-%m-%d")
                            if chunk.published_at
                            else "Recent"
                        ),
                    },
                })

        except Exception as e:
            logger.warning("bm25_ca_chunk_search_failed", error=str(e))

        return results
