"""
engines/book_content/services/retrieval_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Hybrid RAG Retrieval Service — Phase E3

Public API:
  hybrid_search(query, topic_id, subject_id, limit)
      → BM25 keyword + semantic vector + Reciprocal Rank Fusion
  keyword_search(query, topic_id, subject_id, limit)
      → Pure BM25 via tsvector GIN index on BookChunk.search_vector
  semantic_search(query, topic_id, subject_id, limit)
      → Pure cosine similarity via HNSW index on content_embedding.vector
  find_similar_articles(article_id, limit)
      → Article-level similarity via book_article embeddings
  get_rag_context(query, topic_id, max_chunks)
      → Formatted markdown context string ready for LLM injection

Architecture:
  BM25:      PostgreSQL tsvector + GIN index on BookChunk.search_vector
             Catches exact legal citations — "Article 356", "Schedule VII"
  Semantic:  HNSW index on content_embedding (cosine, 384-dim MiniLM)
             Catches concepts — "emergency powers" → "President's Rule"
  RRF:       Reciprocal Rank Fusion k=60 (Cormack 2009)
             score(d) = Σ 1/(k + rank_in_list)  — parameter-free, proven

Cross-engine rule: this service ONLY reads from book_content and content_embedding.
It NEVER writes. Callers (views, CA synthesis, chatbot) own the write path.
"""

import uuid
from typing import Any, Dict, List, Optional, Tuple

import sentry_sdk
import structlog
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import QuerySet

logger = structlog.get_logger(__name__)

# RRF constant from the original paper — do not change without benchmarking
_RRF_K: int = 60

# Candidate pool multiplier: fetch N×limit candidates per lane before RRF
_CANDIDATE_MULTIPLIER: int = 3


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC: HYBRID SEARCH — main entry point for all callers
# ═══════════════════════════════════════════════════════════════════════════════


def hybrid_search(
    query: str,
    topic_id: Optional[uuid.UUID] = None,
    subject_id: Optional[uuid.UUID] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Hybrid BM25 + Semantic search with Reciprocal Rank Fusion.

    Args:
        query:      Natural language or keyword query string.
        topic_id:   Optional — restrict to chunks belonging to one topic.
        subject_id: Optional — restrict to chunks belonging to one subject.
        limit:      Number of results to return (default 10).

    Returns:
        List of dicts, each containing:
          chunk_id, book_content_id, topic_id, topic_name, subject_name,
          chunk_text, chunk_index, source_type, quality_flag,
          rrf_score, bm25_rank, semantic_rank

    Performance:
        Both search lanes run against indexed columns.
        RRF merge is in-memory (max 2×candidate_pool items).
        At 500k chunks: expected <150ms end-to-end.
    """
    if not query or not query.strip():
        logger.warning("hybrid_search_empty_query")
        return []

    candidate_limit = limit * _CANDIDATE_MULTIPLIER

    try:
        # ── Lane 1: BM25 keyword search ───────────────────────────────────────
        bm25_ranked = keyword_search(
            query, topic_id=topic_id, subject_id=subject_id, limit=candidate_limit
        )
        bm25_ids = [row[0] for row in bm25_ranked]

        # ── Lane 2: Semantic vector search ────────────────────────────────────
        semantic_ranked = semantic_search(
            query, topic_id=topic_id, subject_id=subject_id, limit=candidate_limit
        )
        semantic_ids = [row[0] for row in semantic_ranked]

        # ── RRF merge ─────────────────────────────────────────────────────────
        fused = _reciprocal_rank_fusion(bm25_ids, semantic_ids)
        top_ids = [chunk_id for chunk_id, _ in fused[:limit]]
        rrf_scores = {chunk_id: score for chunk_id, score in fused[:limit]}
        bm25_rank_map = {cid: rank for rank, cid in enumerate(bm25_ids, 1)}
        semantic_rank_map = {cid: rank for rank, cid in enumerate(semantic_ids, 1)}

        # ── Fetch BookChunk objects for top IDs ───────────────────────────────
        from engines.book_content.models import BookChunk

        chunks_qs = BookChunk.objects.filter(id__in=top_ids).select_related(
            "book_content", "book_content__topic", "book_content__subject"
        )
        chunks_map: Dict[uuid.UUID, Any] = {c.id: c for c in chunks_qs}

        # ── Build result list (preserve RRF order) ────────────────────────────
        results = []
        for chunk_id in top_ids:
            chunk = chunks_map.get(chunk_id)
            if not chunk:
                continue
            results.append(
                {
                    "chunk_id": str(chunk.id),
                    "book_content_id": str(chunk.book_content_id),
                    "topic_id": str(chunk.book_content.topic_id),
                    "topic_name": (
                        chunk.book_content.topic.name
                        if chunk.book_content.topic
                        else ""
                    ),
                    "subject_name": (
                        chunk.book_content.subject.name
                        if chunk.book_content.subject
                        else ""
                    ),
                    "chunk_text": chunk.chunk_text,
                    "chunk_index": chunk.chunk_index,
                    "source_type": chunk.source_type,
                    "quality_flag": chunk.quality_flag,
                    "rrf_score": round(rrf_scores.get(chunk_id, 0.0), 6),
                    "bm25_rank": bm25_rank_map.get(chunk_id),
                    "semantic_rank": semantic_rank_map.get(chunk_id),
                }
            )

        logger.info(
            "hybrid_search_complete",
            query=query[:80],
            topic_id=str(topic_id) if topic_id else None,
            bm25_candidates=len(bm25_ids),
            semantic_candidates=len(semantic_ids),
            returned=len(results),
        )
        return results

    except Exception as e:
        logger.error("hybrid_search_failed", query=query[:80], error=str(e))
        sentry_sdk.capture_exception(e)
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC: BM25 KEYWORD SEARCH
# ═══════════════════════════════════════════════════════════════════════════════


def keyword_search(
    query: str,
    topic_id: Optional[uuid.UUID] = None,
    subject_id: Optional[uuid.UUID] = None,
    limit: int = 20,
) -> List[Tuple[uuid.UUID, float]]:
    """
    BM25 full-text search via PostgreSQL tsvector + GIN index.

    Uses the pre-computed search_vector column on BookChunk (populated by
    ingestor_service after every article save). Catches exact legal terms,
    proper nouns, article numbers — "Article 356", "Rajya Sabha", etc.

    Returns:
        List of (chunk_id, rank_score) tuples, ordered by rank descending.
    """
    from engines.book_content.models import BookChunk

    if not query or not query.strip():
        return []

    try:
        search_query = SearchQuery(query, config="english", search_type="websearch")

        qs: QuerySet = BookChunk.objects.filter(search_vector=search_query).annotate(
            rank=SearchRank("search_vector", search_query, weights=[0.2, 0.4, 0.6, 1.0])
        )

        if topic_id:
            qs = qs.filter(book_content__topic_id=topic_id)
        if subject_id:
            qs = qs.filter(book_content__subject_id=subject_id)

        qs = qs.filter(search_vector__isnull=False).order_by("-rank")[:limit]

        results = [(row.id, float(row.rank)) for row in qs]
        logger.debug(
            "keyword_search_done",
            query=query[:80],
            hits=len(results),
        )
        return results

    except Exception as e:
        logger.error("keyword_search_failed", query=query[:80], error=str(e))
        sentry_sdk.capture_exception(e)
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC: SEMANTIC VECTOR SEARCH
# ═══════════════════════════════════════════════════════════════════════════════


def semantic_search(
    query: str,
    topic_id: Optional[uuid.UUID] = None,
    subject_id: Optional[uuid.UUID] = None,
    limit: int = 20,
) -> List[Tuple[uuid.UUID, float]]:
    """
    Semantic search via pgvector cosine similarity + HNSW index.

    Generates a query embedding, then finds nearest BookChunk embeddings
    in the content_embedding table (content_type='book_chunk').
    Catches conceptual matches — "emergency powers" finds "President's Rule".

    Returns:
        List of (chunk_id, similarity_score) tuples, ordered by similarity
        descending (1.0 = identical, 0.0 = orthogonal).
    """
    from pgvector.django import CosineDistance

    from engines.book_content.models import BookChunk
    from engines.content.models import Embedding
    from engines.content.services.embedding_service import EmbeddingService

    if not query or not query.strip():
        return []

    try:
        # Generate query vector (HF API or local model)
        query_vector = EmbeddingService.generate_embedding(query)

        # ── Find nearest chunk embeddings via HNSW ────────────────────────────
        # Cosine distance: 0 = identical, 2 = opposite → similarity = 1 - distance
        emb_qs = (
            Embedding.objects.filter(content_type="book_chunk")
            .annotate(distance=CosineDistance("vector", query_vector))
            .order_by("distance")
        )

        # ── Optional topic/subject filter via BookChunk FK ────────────────────
        if topic_id or subject_id:
            # Restrict to chunk IDs that belong to the requested scope
            chunk_filter_qs = BookChunk.objects.all()
            if topic_id:
                chunk_filter_qs = chunk_filter_qs.filter(
                    book_content__topic_id=topic_id
                )
            if subject_id:
                chunk_filter_qs = chunk_filter_qs.filter(
                    book_content__subject_id=subject_id
                )
            valid_chunk_ids = chunk_filter_qs.values_list("id", flat=True)
            emb_qs = emb_qs.filter(content_id__in=valid_chunk_ids)

        emb_qs = emb_qs[:limit]

        results = [
            (row.content_id, round(1.0 - float(row.distance), 6)) for row in emb_qs
        ]
        logger.debug(
            "semantic_search_done",
            query=query[:80],
            hits=len(results),
        )
        return results

    except Exception as e:
        logger.error("semantic_search_failed", query=query[:80], error=str(e))
        sentry_sdk.capture_exception(e)
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC: FIND SIMILAR ARTICLES
# ═══════════════════════════════════════════════════════════════════════════════


def find_similar_articles(
    article_id: uuid.UUID,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Find BookContent articles semantically similar to a given article.

    Uses article-level embeddings (content_type='book_article') stored in
    content_embedding. These are generated by ingestor_service from the
    first 1200 chars of each article.

    Use cases:
      - "You might also like" recommendations
      - CA synthesis: find book articles related to a news event
      - Cross-topic concept linking

    Returns:
        List of dicts with article metadata + similarity_score, sorted by
        similarity descending.
    """
    from pgvector.django import CosineDistance

    from engines.book_content.models import BookContent
    from engines.content.models import Embedding

    try:
        # Get the source article's embedding
        source_emb = Embedding.objects.filter(
            content_type="book_article",
            content_id=article_id,
        ).first()

        if not source_emb:
            logger.warning(
                "find_similar_articles_no_embedding", article_id=str(article_id)
            )
            return []

        # Find nearest articles (exclude self)
        similar_embs = (
            Embedding.objects.filter(content_type="book_article")
            .exclude(content_id=article_id)
            .annotate(distance=CosineDistance("vector", source_emb.vector))
            .order_by("distance")[:limit]
        )

        similar_article_ids = [e.content_id for e in similar_embs]
        distance_map = {e.content_id: float(e.distance) for e in similar_embs}

        # Fetch BookContent objects
        articles = BookContent.objects.filter(
            id__in=similar_article_ids
        ).select_related("topic", "subject")
        article_map = {a.id: a for a in articles}

        results = []
        for article_id_sim in similar_article_ids:
            article = article_map.get(article_id_sim)
            if not article:
                continue
            distance = distance_map.get(article_id_sim, 1.0)
            results.append(
                {
                    "article_id": str(article.id),
                    "topic_name": article.topic.name if article.topic else "",
                    "subject_name": article.subject.name if article.subject else "",
                    "word_count": article.word_count,
                    "quality_score": article.quality_score,
                    "similarity_score": round(1.0 - distance, 6),
                }
            )

        logger.info(
            "find_similar_articles_complete",
            source_article=str(article_id),
            returned=len(results),
        )
        return results

    except Exception as e:
        logger.error(
            "find_similar_articles_failed", article_id=str(article_id), error=str(e)
        )
        sentry_sdk.capture_exception(e)
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC: GET RAG CONTEXT (high-level LLM helper)
# ═══════════════════════════════════════════════════════════════════════════════


def get_rag_context(
    query: str,
    topic_id: Optional[uuid.UUID] = None,
    subject_id: Optional[uuid.UUID] = None,
    max_chunks: int = 5,
) -> str:
    """
    Returns a formatted markdown context string ready for LLM injection.

    Runs hybrid_search, then formats the top chunks as:

        ## Context from Knowledge Base

        ### [1] Fundamental Rights — Indian Constitution & Polity
        <chunk text>

        ### [2] ...

    Designed to be injected into any LLM prompt as the RAG context block.
    Callers are responsible for the prompt template around this context.

    Returns:
        Formatted string (empty string if no results found).
    """
    chunks = hybrid_search(
        query,
        topic_id=topic_id,
        subject_id=subject_id,
        limit=max_chunks,
    )

    if not chunks:
        logger.warning("get_rag_context_no_results", query=query[:80])
        return ""

    lines = ["## Context from Knowledge Base\n"]
    for i, chunk in enumerate(chunks, 1):
        topic = chunk.get("topic_name", "Unknown Topic")
        subject = chunk.get("subject_name", "")
        header = f"### [{i}] {topic}"
        if subject:
            header += f" — {subject}"
        lines.append(header)
        lines.append(chunk["chunk_text"])
        lines.append("")  # blank line between chunks

    context = "\n".join(lines).strip()
    logger.info(
        "get_rag_context_complete",
        query=query[:80],
        chunks_used=len(chunks),
        context_chars=len(context),
    )
    return context


# ═══════════════════════════════════════════════════════════════════════════════
# PRIVATE: RECIPROCAL RANK FUSION
# ═══════════════════════════════════════════════════════════════════════════════


def _reciprocal_rank_fusion(
    bm25_ids: List[uuid.UUID],
    semantic_ids: List[uuid.UUID],
    k: int = _RRF_K,
) -> List[Tuple[uuid.UUID, float]]:
    """
    Reciprocal Rank Fusion (Cormack, Clarke & Buettcher, 2009).

    score(doc) = Σ_list  1 / (k + rank_in_list)

    k=60 is the standard constant from the paper. A document ranked 1st
    in both lists scores 2/61 ≈ 0.033; ranked 60th in both scores 2/120 ≈ 0.017.
    Documents appearing in only one list still get partial credit.

    Args:
        bm25_ids:     Chunk UUIDs ordered by BM25 rank (best first).
        semantic_ids: Chunk UUIDs ordered by semantic similarity (best first).
        k:            Smoothing constant (default 60).

    Returns:
        List of (chunk_id, rrf_score) sorted by score descending.
    """
    scores: Dict[uuid.UUID, float] = {}

    for rank, chunk_id in enumerate(bm25_ids, 1):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)

    for rank, chunk_id in enumerate(semantic_ids, 1):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


# ═══════════════════════════════════════════════════════════════════════════════
# E5: CA ↔ BOOK CONTENT CROSS-SOURCE LINKING
# ═══════════════════════════════════════════════════════════════════════════════
#
# Architecture:
#   content_embedding (content_type='ca_chunk')  ←── vector proximity ──→
#   content_embedding (content_type='book_article')
#
# Three layers of cross-source intelligence:
#
#   1. find_book_articles_for_ca(ca_article_id)
#      Dynamic retrieval — given a CA article, return relevant Book articles.
#      Used by: CA synthesis service, "📚 Study Material" UI panel.
#
#   2. find_ca_for_book_article(book_content_id)
#      Dynamic retrieval — given a Book article, return recent CA articles on same topic.
#      Used by: Knowledge Map "📰 In the News" side-panel.
#
#   3. create_cross_links_for_book_article(book_content_obj)
#      Persistent storage — creates TopicRelation(relation_type="cross_subject") records.
#      Called by ingestor after every article generation.
#      Powers the knowledge graph UI edges between CA topics and Book topics.
#
#   4. get_ca_synthesis_context(ca_article_id)
#      All-in-one RAG context builder for CA synthesis LLM calls.
#      Returns formatted markdown: "Here is relevant static knowledge..."
#      Called directly by the CA synthesis service.
#
# Similarity threshold: 0.70 cosine similarity for persistent links (quality bar).
# Dynamic retrieval uses 0.50 threshold (wider net, filtered per caller's needs).
# ═══════════════════════════════════════════════════════════════════════════════

_CA_BOOK_LINK_THRESHOLD: float = 0.70  # for persistent TopicRelation records
_CA_BOOK_QUERY_THRESHOLD: float = 0.50  # for dynamic retrieval (wider)
_CA_BOOK_LINK_LIMIT: int = 10  # max CA chunks to consider per book article


def find_book_articles_for_ca(
    ca_article_id: uuid.UUID,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Given a CA article, find semantically related BookContent articles.

    Strategy:
      1. Fetch all CAChunk IDs for this CA article.
      2. Get their embeddings from content_embedding.
      3. Compute centroid vector (mean of all chunk vectors) — more representative
         than using a single chunk.
      4. Find nearest book_article embeddings (HNSW, cosine distance).
      5. Return BookContent metadata with similarity scores.

    Used by:
      - CA synthesis service: "pull book knowledge as LLM context for this news"
      - Frontend: "📚 Study Material" panel under CA article detail page

    Returns:
        List of dicts — article_id, topic_name, subject_name, word_count,
        quality_score, similarity_score. Sorted by similarity descending.
    """
    from pgvector.django import CosineDistance

    from engines.book_content.models import BookContent
    from engines.content.models import Embedding
    from engines.current_affairs.models import CAChunk

    try:
        # ── Step 1: Get CA chunk IDs for this article ─────────────────────────
        ca_chunk_ids = list(
            CAChunk.objects.filter(ca_article_id=ca_article_id)
            .order_by("chunk_index")
            .values_list("id", flat=True)
        )
        if not ca_chunk_ids:
            logger.warning(
                "find_book_for_ca_no_chunks", ca_article_id=str(ca_article_id)
            )
            return []

        # ── Step 2: Fetch their embeddings ───────────────────────────────────
        ca_embs = list(
            Embedding.objects.filter(
                content_type="ca_chunk",
                content_id__in=ca_chunk_ids,
            ).values_list("vector", flat=True)
        )
        if not ca_embs:
            logger.warning(
                "find_book_for_ca_no_embeddings", ca_article_id=str(ca_article_id)
            )
            return []

        # ── Step 3: Compute centroid vector (mean of all chunk vectors) ───────
        centroid = _mean_vector(ca_embs)

        # ── Step 4: Find nearest book_article embeddings (HNSW) ──────────────
        book_embs = (
            Embedding.objects.filter(content_type="book_article")
            .annotate(distance=CosineDistance("vector", centroid))
            .order_by("distance")[: limit * 2]  # fetch extra, filter noise in Python
        )

        # ── Step 5: Build results above dynamic threshold ─────────────────────
        book_ids_ordered = []
        distance_map: Dict[uuid.UUID, float] = {}
        for emb in book_embs:
            sim = 1.0 - float(emb.distance)
            if sim >= _CA_BOOK_QUERY_THRESHOLD:
                book_ids_ordered.append(emb.content_id)
                distance_map[emb.content_id] = float(emb.distance)

        if not book_ids_ordered:
            logger.info(
                "find_book_for_ca_no_matches_above_threshold",
                ca_article_id=str(ca_article_id),
                threshold=_CA_BOOK_QUERY_THRESHOLD,
            )
            return []

        articles = BookContent.objects.filter(id__in=book_ids_ordered).select_related(
            "topic", "subject"
        )
        article_map = {a.id: a for a in articles}

        results = []
        for book_id in book_ids_ordered[:limit]:
            art = article_map.get(book_id)
            if not art:
                continue
            results.append(
                {
                    "article_id": str(art.id),
                    "topic_id": str(art.topic_id) if art.topic_id else None,
                    "topic_name": art.topic.name if art.topic else "",
                    "subject_name": art.subject.name if art.subject else "",
                    "word_count": art.word_count,
                    "quality_score": float(art.quality_score or 0),
                    "similarity_score": round(1.0 - distance_map[book_id], 6),
                    "knowledge_map_url": (
                        f"/knowledge?topic={art.topic_id}"
                        if art.topic_id
                        else "/knowledge"
                    ),
                }
            )

        logger.info(
            "find_book_for_ca_complete",
            ca_article_id=str(ca_article_id),
            returned=len(results),
        )
        return results

    except Exception as e:
        logger.error(
            "find_book_for_ca_failed",
            ca_article_id=str(ca_article_id),
            error=str(e),
        )
        sentry_sdk.capture_exception(e)
        return []


def find_ca_for_book_article(
    book_content_id: uuid.UUID,
    limit: int = 5,
    days_recent: int = 90,
) -> List[Dict[str, Any]]:
    """
    Given a BookContent article, find recent CA articles on the same topic.

    Strategy:
      1. Get book_article embedding from content_embedding.
      2. Find nearest ca_chunk embeddings (HNSW).
      3. Resolve ca_chunks → parent CAArticles (deduplicated).
      4. Filter to recent articles only (within days_recent, default 90 days).

    Used by:
      - Knowledge Map "📰 In the News" side-panel — "Current Affairs related to
        this topic" shown alongside the book article.
      - Contextualises static book knowledge with live news events.

    Args:
        days_recent: Only return CA articles published within this many days.
                     Pass 0 to skip recency filter (return all time).

    Returns:
        List of dicts — ca_article_id, title, source, published_at,
        ca_url, similarity_score. Sorted by similarity descending.
    """
    from pgvector.django import CosineDistance

    from engines.content.models import Embedding
    from engines.current_affairs.models import CAChunk

    try:
        # ── Step 1: Get book_article embedding ───────────────────────────────
        book_emb = Embedding.objects.filter(
            content_type="book_article",
            content_id=book_content_id,
        ).first()

        if not book_emb:
            logger.warning(
                "find_ca_for_book_no_embedding",
                book_content_id=str(book_content_id),
            )
            return []

        # ── Step 2: Find nearest ca_chunk embeddings (HNSW) ──────────────────
        ca_embs = list(
            Embedding.objects.filter(content_type="ca_chunk")
            .annotate(distance=CosineDistance("vector", book_emb.vector))
            .order_by("distance")[: _CA_BOOK_LINK_LIMIT * 3]
        )

        # ── Step 3: Filter by threshold and resolve to CAChunks ──────────────
        ca_chunk_ids_above = [
            e.content_id
            for e in ca_embs
            if (1.0 - float(e.distance)) >= _CA_BOOK_QUERY_THRESHOLD
        ]
        distance_by_chunk = {e.content_id: float(e.distance) for e in ca_embs}

        if not ca_chunk_ids_above:
            return []

        ca_chunks = CAChunk.objects.filter(id__in=ca_chunk_ids_above).select_related(
            "ca_article", "ca_article__source"
        )

        # ── Step 4: Deduplicate by parent CAArticle, pick best similarity ─────
        best_by_article: Dict[uuid.UUID, Dict] = {}
        for chunk in ca_chunks:
            ca = chunk.ca_article
            if not ca:
                continue
            sim = round(1.0 - distance_by_chunk.get(chunk.id, 1.0), 6)
            existing = best_by_article.get(ca.id)
            if not existing or sim > existing["similarity_score"]:
                best_by_article[ca.id] = {
                    "ca_article_id": str(ca.id),
                    "title": ca.title,
                    "source": ca.source.name if ca.source else "",
                    "published_at": (
                        ca.published_at.strftime("%Y-%m-%d") if ca.published_at else ""
                    ),
                    "ca_url": f"/current-affairs/{ca.id}",
                    "similarity_score": sim,
                    "_published_at_dt": ca.published_at,
                }

        results = list(best_by_article.values())

        # ── Step 5: Recency filter ────────────────────────────────────────────
        if days_recent > 0:
            from datetime import datetime, timedelta, timezone

            cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days_recent)
            results = [
                r
                for r in results
                if r["_published_at_dt"] and r["_published_at_dt"] >= cutoff
            ]

        # Clean internal date field before returning
        for r in results:
            r.pop("_published_at_dt", None)

        results.sort(key=lambda x: x["similarity_score"], reverse=True)

        logger.info(
            "find_ca_for_book_complete",
            book_content_id=str(book_content_id),
            returned=len(results[:limit]),
        )
        return results[:limit]

    except Exception as e:
        logger.error(
            "find_ca_for_book_failed",
            book_content_id=str(book_content_id),
            error=str(e),
        )
        sentry_sdk.capture_exception(e)
        return []


def create_cross_links_for_book_article(
    book_content_obj: "BookContent",  # type: ignore[name-defined]  # noqa: F821
) -> int:
    """
    Persistent cross-linking: creates TopicRelation(relation_type="cross_subject").

    Called by ingestor_service after every BookContent is generated.
    Also callable manually for backfilling existing articles.

    Pipeline:
      1. Get book_article embedding.
      2. Find nearest ca_chunk embeddings (threshold: 0.70 — quality bar).
      3. For each matching CA chunk:
         a. Look up CATopicLink → knowledge.Topic for that CA chunk.
         b. If topic found AND book_content.topic exists:
            → update_or_create TopicRelation(
                  source_topic = ca_topic,
                  target_topic = book_content.topic,
                  relation_type = "cross_subject",
                  similarity_score = best_score,
                  is_auto_detected = True,
              )
      4. Return count of new/updated TopicRelation records.

    Why TopicRelation (not a new table):
      Both CA chunks and BookContent already map to knowledge.Topic nodes.
      TopicRelation is exactly the right model for cross-topic edges.
      The knowledge graph UI already reads TopicRelation for edges.
      relation_type="cross_subject" makes these visually distinct edges.

    Idempotent: update_or_create ensures re-running never creates duplicates.
    Graceful: if CATopicLink has no data yet (early stage), returns 0 silently.
    """
    from pgvector.django import CosineDistance

    from engines.book_content.models import TopicRelation
    from engines.content.models import Embedding
    from engines.current_affairs.models import CATopicLink

    links_created = 0

    try:
        if not book_content_obj.topic_id:
            logger.warning(
                "cross_link_skip_no_topic",
                book_content_id=str(book_content_obj.id),
            )
            return 0

        # ── Step 1: Get book_article embedding ───────────────────────────────
        book_emb = Embedding.objects.filter(
            content_type="book_article",
            content_id=book_content_obj.id,
        ).first()

        if not book_emb:
            logger.warning(
                "cross_link_skip_no_embedding",
                book_content_id=str(book_content_obj.id),
            )
            return 0

        # ── Step 2: Find nearest ca_chunk embeddings above threshold ─────────
        ca_embs = list(
            Embedding.objects.filter(content_type="ca_chunk")
            .annotate(distance=CosineDistance("vector", book_emb.vector))
            .order_by("distance")[:_CA_BOOK_LINK_LIMIT]
        )

        above_threshold = [
            (e.content_id, round(1.0 - float(e.distance), 6))
            for e in ca_embs
            if (1.0 - float(e.distance)) >= _CA_BOOK_LINK_THRESHOLD
        ]

        if not above_threshold:
            logger.info(
                "cross_link_no_matches",
                book_content_id=str(book_content_obj.id),
                threshold=_CA_BOOK_LINK_THRESHOLD,
            )
            return 0

        ca_chunk_id_to_score: Dict[uuid.UUID, float] = {
            cid: score for cid, score in above_threshold
        }

        # ── Step 3: Resolve CA chunks → Topics via CATopicLink ───────────────
        # One bulk query for all matched CA chunks — no N+1
        topic_links = (
            CATopicLink.objects.filter(
                ca_chunk_id__in=list(ca_chunk_id_to_score.keys())
            )
            .select_related("topic")
            .order_by("-relevance_score")
        )

        # Best score per CA topic (a topic may appear via multiple CA chunks)
        best_score_per_ca_topic: Dict[uuid.UUID, float] = {}
        for tl in topic_links:
            ca_topic_id: uuid.UUID = tl.topic_id
            chunk_score = ca_chunk_id_to_score.get(tl.ca_chunk_id, 0.0)
            if chunk_score > best_score_per_ca_topic.get(ca_topic_id, 0.0):
                best_score_per_ca_topic[ca_topic_id] = chunk_score

        if not best_score_per_ca_topic:
            logger.info(
                "cross_link_no_topic_links_found",
                book_content_id=str(book_content_obj.id),
                ca_chunks_matched=len(above_threshold),
                note="CATopicLink table may be empty — links will be created once CA pipeline populates it",
            )
            return 0

        # ── Step 4: Create/update TopicRelation records ───────────────────────
        book_topic_id: uuid.UUID = book_content_obj.topic_id

        for ca_topic_id, best_score in best_score_per_ca_topic.items():
            # Avoid self-loop (ca_topic == book_topic)
            if ca_topic_id == book_topic_id:
                continue

            try:
                _, created = TopicRelation.objects.update_or_create(
                    source_topic_id=ca_topic_id,
                    target_topic_id=book_topic_id,
                    defaults={
                        "relation_type": "cross_subject",
                        "similarity_score": best_score,
                        "is_auto_detected": True,
                    },
                )
                links_created += 1
                logger.debug(
                    "cross_link_created" if created else "cross_link_updated",
                    ca_topic_id=str(ca_topic_id),
                    book_topic_id=str(book_topic_id),
                    score=best_score,
                )
            except Exception as link_err:
                # unique_together violation or other DB error — log and continue
                logger.warning(
                    "cross_link_single_failed",
                    ca_topic_id=str(ca_topic_id),
                    book_topic_id=str(book_topic_id),
                    error=str(link_err),
                )

        logger.info(
            "cross_link_complete",
            book_content_id=str(book_content_obj.id),
            topic=book_content_obj.topic.name if book_content_obj.topic else "",
            links_created=links_created,
        )
        return links_created

    except Exception as e:
        logger.error(
            "cross_link_failed",
            book_content_id=str(book_content_obj.id),
            error=str(e),
        )
        sentry_sdk.capture_exception(e)
        return 0


def get_ca_synthesis_context(
    ca_article_id: uuid.UUID,
    max_book_articles: int = 3,
    max_chunks_per_article: int = 2,
) -> str:
    """
    All-in-one RAG context builder for CA synthesis LLM calls.

    Finds the most relevant BookContent articles for a given CA article,
    fetches their top chunks, and formats them as a single markdown context
    block ready for injection into an LLM prompt.

    Format:
        ## Static Knowledge Base — Relevant Background

        ### [1] Parliament of India — Indian Constitution & Polity
        (similarity: 0.847)
        <chunk text 1>

        <chunk text 2>

        ### [2] ...

    Called by: CA synthesis service (future feature).
    Also useful for: RAG chatbot when user asks about a news event.

    Args:
        max_book_articles:    Max number of book articles to include (default 3).
        max_chunks_per_article: Max chunks to include per article (default 2).

    Returns:
        Formatted string (empty string if no relevant book content found).
    """
    try:
        # ── Find relevant book articles ───────────────────────────────────────
        book_articles = find_book_articles_for_ca(
            ca_article_id, limit=max_book_articles
        )

        if not book_articles:
            logger.info(
                "ca_synthesis_context_empty",
                ca_article_id=str(ca_article_id),
            )
            return ""

        # ── Fetch top chunks per book article via hybrid search ───────────────
        lines = ["## Static Knowledge Base — Relevant Background\n"]

        for i, book in enumerate(book_articles, 1):
            topic_name = book.get("topic_name", "Unknown Topic")
            subject_name = book.get("subject_name", "")
            similarity = book.get("similarity_score", 0.0)

            header = f"### [{i}] {topic_name}"
            if subject_name:
                header += f" — {subject_name}"
            header += f"\n*(relevance: {similarity:.3f})*"
            lines.append(header)

            # Get best chunks for this article using hybrid search on topic name
            # topic_id scopes results to only this article's chunks
            topic_id = book.get("topic_id")
            chunks = hybrid_search(
                query=topic_name,
                topic_id=uuid.UUID(topic_id) if topic_id else None,
                limit=max_chunks_per_article,
            )

            for chunk in chunks:
                lines.append(chunk["chunk_text"])
                lines.append("")  # blank line between chunks

        context = "\n".join(lines).strip()
        logger.info(
            "ca_synthesis_context_built",
            ca_article_id=str(ca_article_id),
            book_articles_used=len(book_articles),
            context_chars=len(context),
        )
        return context

    except Exception as e:
        logger.error(
            "ca_synthesis_context_failed",
            ca_article_id=str(ca_article_id),
            error=str(e),
        )
        sentry_sdk.capture_exception(e)
        return ""


# ═══════════════════════════════════════════════════════════════════════════════
# PRIVATE: VECTOR MATH UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════


def create_book_inter_subject_links(
    book_content_obj: "BookContent",  # type: ignore[name-defined]  # noqa: F821
) -> int:
    """
    Creates TopicRelation edges between BookContent articles from DIFFERENT subjects
    that are semantically similar — the cross-subject web.

    Examples of what this creates:
      "Union Budget" (Economy) ──cross_subject──▶ "Parliamentary Budget Process" (Polity)
      "Emergency Provisions" (Polity) ──cross_subject──▶ "Disaster Management" (Governance)
      "River Systems" (Geography) ──cross_subject──▶ "Water Disputes Tribunal" (Polity)

    Why this is valuable for UPSC:
      UPSC questions routinely connect concepts across subjects.
      "Discuss the economic implications of Article 356" — Polity + Economy.
      This function builds those cross-subject edges automatically via embeddings.

    What it does NOT create:
      - same-subject links (those are "related_to", handled separately)
      - links below the 0.65 threshold (noise prevention)
      - self-loops (source == target)
      - duplicate edges (update_or_create — idempotent)

    Bidirectional: creates BOTH A→B and B→A edges so graph traversal works
    in either direction without assumptions about directionality.

    Threshold: 0.65 cosine similarity — lower than CA↔Book (0.70) because
    cross-subject conceptual similarity is naturally slightly weaker than
    same-domain CA↔Book similarity.

    Called by: ingestor_service after every article generation.
    Never raises — failure must not abort ingestion pipeline.

    Returns:
        Number of TopicRelation records created or updated.
    """
    from pgvector.django import CosineDistance

    from engines.book_content.models import BookContent, TopicRelation
    from engines.content.models import Embedding

    # Threshold for cross-subject book-to-book links (slightly relaxed vs CA↔Book)
    _INTER_SUBJECT_THRESHOLD: float = 0.65
    _INTER_SUBJECT_LIMIT: int = 15  # candidate book articles to evaluate

    links_created = 0

    try:
        if not book_content_obj.topic_id or not book_content_obj.subject_id:
            logger.warning(
                "inter_subject_skip_no_topic_or_subject",
                book_content_id=str(book_content_obj.id),
            )
            return 0

        # ── Step 1: Get this article's book_article embedding ─────────────────
        book_emb = Embedding.objects.filter(
            content_type="book_article",
            content_id=book_content_obj.id,
        ).first()

        if not book_emb:
            logger.warning(
                "inter_subject_skip_no_embedding",
                book_content_id=str(book_content_obj.id),
            )
            return 0

        # ── Step 2: Find nearest book_article embeddings ──────────────────────
        # Exclude self — content_id != book_content_obj.id
        nearest_embs = list(
            Embedding.objects.filter(content_type="book_article")
            .exclude(content_id=book_content_obj.id)
            .annotate(distance=CosineDistance("vector", book_emb.vector))
            .order_by("distance")[:_INTER_SUBJECT_LIMIT]
        )

        above_threshold = [
            (e.content_id, round(1.0 - float(e.distance), 6))
            for e in nearest_embs
            if (1.0 - float(e.distance)) >= _INTER_SUBJECT_THRESHOLD
        ]

        if not above_threshold:
            logger.info(
                "inter_subject_no_matches",
                book_content_id=str(book_content_obj.id),
                threshold=_INTER_SUBJECT_THRESHOLD,
            )
            return 0

        # ── Step 3: Fetch similar BookContent objects ─────────────────────────
        similar_ids = [cid for cid, _ in above_threshold]
        score_map: Dict[uuid.UUID, float] = {cid: s for cid, s in above_threshold}

        similar_articles = BookContent.objects.filter(
            id__in=similar_ids
        ).select_related("topic", "subject")

        # ── Step 4: Create bidirectional TopicRelation edges ──────────────────
        source_topic_id: uuid.UUID = book_content_obj.topic_id
        source_subject_id = book_content_obj.subject_id

        for article in similar_articles:
            if not article.topic_id:
                continue

            target_topic_id: uuid.UUID = article.topic_id
            score = score_map.get(article.id, 0.0)

            # Determine relation_type:
            # cross_subject = different subjects (the interesting case for UPSC)
            # related_to    = same subject, different topic
            is_cross_subject = (
                article.subject_id and article.subject_id != source_subject_id
            )
            rel_type = "cross_subject" if is_cross_subject else "related_to"

            # ── A → B edge ────────────────────────────────────────────────────
            try:
                _, created_ab = TopicRelation.objects.update_or_create(
                    source_topic_id=source_topic_id,
                    target_topic_id=target_topic_id,
                    defaults={
                        "relation_type": rel_type,
                        "similarity_score": score,
                        "is_auto_detected": True,
                    },
                )
                links_created += 1
            except Exception as e_ab:
                logger.warning(
                    "inter_subject_link_ab_failed",
                    source=str(source_topic_id),
                    target=str(target_topic_id),
                    error=str(e_ab),
                )

            # ── B → A edge (bidirectional — graph traversal works both ways) ──
            try:
                _, created_ba = TopicRelation.objects.update_or_create(
                    source_topic_id=target_topic_id,
                    target_topic_id=source_topic_id,
                    defaults={
                        "relation_type": rel_type,
                        "similarity_score": score,
                        "is_auto_detected": True,
                    },
                )
                links_created += 1
            except Exception as e_ba:
                logger.warning(
                    "inter_subject_link_ba_failed",
                    source=str(target_topic_id),
                    target=str(source_topic_id),
                    error=str(e_ba),
                )

            logger.debug(
                "inter_subject_link_created",
                source_topic=book_content_obj.topic.name
                if book_content_obj.topic
                else "",
                target_topic=article.topic.name if article.topic else "",
                source_subject=book_content_obj.subject.name
                if book_content_obj.subject
                else "",
                target_subject=article.subject.name if article.subject else "",
                relation_type=rel_type,
                score=score,
            )

        logger.info(
            "inter_subject_links_complete",
            book_content_id=str(book_content_obj.id),
            topic=book_content_obj.topic.name if book_content_obj.topic else "",
            subject=book_content_obj.subject.name if book_content_obj.subject else "",
            links_created=links_created,
        )
        return links_created

    except Exception as e:
        logger.error(
            "inter_subject_links_failed",
            book_content_id=str(book_content_obj.id),
            error=str(e),
        )
        sentry_sdk.capture_exception(e)
        return 0


def _mean_vector(vectors: List[List[float]]) -> List[float]:
    """
    Compute element-wise mean of a list of equal-length float vectors.

    Used to produce a single "centroid" embedding for a CA article from its
    multiple chunk embeddings. The centroid is more representative than any
    single chunk, especially for long articles with varied content.

    Pure Python (no numpy) — correct for 384-dim MiniLM vectors.
    O(n × 384) — negligible for typical CA article chunk counts (3-10).
    """
    n = len(vectors)
    if n == 0:
        return []
    if n == 1:
        return vectors[0]
    dim = len(vectors[0])
    return [sum(vectors[i][j] for i in range(n)) / n for j in range(dim)]


# ═══════════════════════════════════════════════════════════════════════════════
# RAG GROUNDING GATEWAY — Phase 1
# Single entry point every content generator calls to get its grounding.
# ═══════════════════════════════════════════════════════════════════════════════
#
# retrieve_grounding(query, seed_topic_id, ...) is THE grounding source for
# daily_ca, daily_quiz, quiz_generator and article_generation. Design:
#   • publish-agnostic — reads BookChunk/Embedding directly (sidesteps the
#                        is_published gate that left daily_ca with 0 grounding).
#   • semantic + graph — cosine recall over book_chunk + ca_chunk, then expanded
#                        along TopicRelation edges (cross_subject / related_to).
#   • relevance-gated  — drops anything beyond GROUNDING_DISTANCE_THRESHOLD.
#                        Relevance is the boundary, NOT subject — cross-subject is
#                        desired (Budget→Polity), out-of-context is cut.
#   • db-alias aware   — honours 'default' (== Supabase on Render) or 'supabase'.
#   • never raises     — any failure returns an empty result so the caller falls
#                        back to its own wiki path.
#
# Returns a neutral GroundingResult dict; the two thin adapters at the bottom
# (as_static_facts / as_wiki_enrichment) render it into the exact shape each
# existing prompt slot expects, so prompt templates stay unchanged.

# ── Shared retrieval constants (Phase 2 aligns these with knowledge.search_service) ──
GROUNDING_DISTANCE_THRESHOLD: float = (
    0.62  # cosine-distance noise floor (== search_service._NOISE_THRESHOLD)
)
K_BOOK_DEFAULT: int = 4  # theory chunks (book_chunk)
K_CA_DEFAULT: int = 4  # recency chunks (ca_chunk)
_GROUNDING_GRAPH_TOPIC_LIMIT: int = 6  # TopicRelation neighbours to expand into
_GROUNDING_CANDIDATE_POOL: int = (
    60  # HNSW candidates fetched before Python threshold filter
)
_GROUNDING_EMBED_CACHE_TTL: int = 3600  # Redis TTL for query embeddings (1h)
_GROUNDING_TEXT_CAP: int = (
    1400  # per-chunk char cap injected into prompts (token guard)
)


def _grounding_query_embedding(query: str) -> Optional[List[float]]:
    """Embed the query string, Redis-cached (mirrors knowledge.search_service)."""
    import hashlib

    from django.core.cache import cache

    from engines.content.services.embedding_service import EmbeddingService

    key = f"qemb:{hashlib.md5(query.strip().lower().encode()).hexdigest()}"
    try:
        cached = cache.get(key)
        if cached is not None:
            return cached
    except Exception:
        pass
    vec = EmbeddingService.generate_embedding(query)
    try:
        cache.set(key, vec, timeout=_GROUNDING_EMBED_CACHE_TTL)
    except Exception:
        pass
    return vec


def _build_seed_query(seed_topic: Any, explicit_query: Optional[str]) -> str:
    """Assemble the retrieval query from explicit text + the seed Topic's own semantics."""
    parts: List[str] = []
    if explicit_query and explicit_query.strip():
        parts.append(explicit_query.strip())
    if seed_topic is not None:
        if getattr(seed_topic, "name", ""):
            parts.append(seed_topic.name)
        if getattr(seed_topic, "description", ""):
            parts.append(seed_topic.description)
        kws = getattr(seed_topic, "keywords", None) or []
        if isinstance(kws, list) and kws:
            parts.append(", ".join(str(k) for k in kws[:12]))
    return " — ".join(p for p in parts if p).strip()


def _semantic_book_chunks(
    query_vector: List[float],
    db_alias: str,
    limit: int,
    restrict_topic_ids: Optional[List[Any]] = None,
) -> List[Tuple[Any, float]]:
    """Cosine recall over book_chunk embeddings. Returns [(chunk_id, distance)] below threshold."""
    from pgvector.django import CosineDistance

    from engines.book_content.models import BookChunk
    from engines.content.models import Embedding

    emb_qs = (
        Embedding.objects.using(db_alias)
        .filter(content_type="book_chunk")
        .annotate(distance=CosineDistance("vector", query_vector))
        .order_by("distance")
    )
    if restrict_topic_ids:
        valid_ids = list(
            BookChunk.objects.using(db_alias)
            .filter(book_content__topic_id__in=list(restrict_topic_ids))
            .values_list("id", flat=True)
        )
        if not valid_ids:
            return []
        emb_qs = emb_qs.filter(content_id__in=valid_ids)

    rows = list(emb_qs[:_GROUNDING_CANDIDATE_POOL])
    scored = [
        (r.content_id, float(r.distance))
        for r in rows
        if float(r.distance) < GROUNDING_DISTANCE_THRESHOLD
    ]
    return scored[:limit]


def _fetch_book_chunk_dicts(
    scored: List[Tuple[Any, float]], db_alias: str
) -> List[Dict[str, Any]]:
    """Resolve scored book_chunk ids to provenance-rich dicts (RRF order preserved)."""
    from engines.book_content.models import BookChunk

    ids = [cid for cid, _ in scored]
    if not ids:
        return []
    objs = {
        c.id: c
        for c in BookChunk.objects.using(db_alias)
        .filter(id__in=ids)
        .select_related("book_content", "book_content__topic", "book_content__subject")
    }
    out: List[Dict[str, Any]] = []
    for cid, dist in scored:
        c = objs.get(cid)
        if not c or not c.book_content:
            continue
        bc = c.book_content
        out.append(
            {
                "content_type": "book_chunk",
                "id": str(c.id),
                "text": (c.chunk_text or "")[:_GROUNDING_TEXT_CAP],
                "topic": bc.topic.name if bc.topic_id else "",
                "topic_id": str(bc.topic_id) if bc.topic_id else None,
                "subject": bc.subject.name if bc.subject_id else "",
                "source_type": c.source_type,
                "score": round(1.0 - dist, 4),
            }
        )
    return out


def _semantic_ca_chunks(
    query_vector: List[float], db_alias: str, limit: int
) -> List[Tuple[Any, float]]:
    """Cosine recall over ca_chunk embeddings. Returns [(chunk_id, distance)] below threshold."""
    from pgvector.django import CosineDistance

    from engines.content.models import Embedding

    rows = list(
        Embedding.objects.using(db_alias)
        .filter(content_type="ca_chunk")
        .annotate(distance=CosineDistance("vector", query_vector))
        .order_by("distance")[:_GROUNDING_CANDIDATE_POOL]
    )
    scored = [
        (r.content_id, float(r.distance))
        for r in rows
        if float(r.distance) < GROUNDING_DISTANCE_THRESHOLD
    ]
    return scored[
        : limit * 3
    ]  # over-fetch; expired/recency filtering happens on resolve


def _fetch_ca_chunk_dicts(
    scored: List[Tuple[Any, float]],
    db_alias: str,
    limit: int,
    recency_days: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Resolve scored ca_chunk ids to dicts (skip expired; optional recency window)."""
    from datetime import timedelta

    from django.utils import timezone

    from engines.current_affairs.models import CAChunk

    ids = [cid for cid, _ in scored]
    if not ids:
        return []
    qs = (
        CAChunk.objects.using(db_alias)
        .filter(id__in=ids, is_expired=False)
        .select_related("ca_article", "ca_article__source")
    )
    if recency_days:
        qs = qs.filter(published_at__gte=timezone.now() - timedelta(days=recency_days))
    objs = {c.id: c for c in qs}

    out: List[Dict[str, Any]] = []
    for cid, dist in scored:
        c = objs.get(cid)
        if not c:
            continue
        ca = c.ca_article
        out.append(
            {
                "content_type": "ca_chunk",
                "id": str(c.id),
                "text": (c.chunk_text or "")[:_GROUNDING_TEXT_CAP],
                "topic": ca.title if ca else "",
                "topic_id": None,
                "subject": ca.source.name if (ca and ca.source_id) else "News",
                "source_type": "ca",
                "date": c.published_at.strftime("%Y-%m-%d") if c.published_at else "",
                "score": round(1.0 - dist, 4),
            }
        )
        if len(out) >= limit:
            break
    return out


def _graph_related_topic_ids(seed_topic_id: Any, db_alias: str) -> List[Any]:
    """TopicRelation neighbours of the seed (cross_subject + related_to), score-ordered."""
    from engines.book_content.models import TopicRelation

    rels = (
        TopicRelation.objects.using(db_alias)
        .filter(source_topic_id=seed_topic_id)
        .order_by("-similarity_score")
        .values_list("target_topic_id", flat=True)[:_GROUNDING_GRAPH_TOPIC_LIMIT]
    )
    return list(rels)


def _rrf_merge(lanes: List[List[Dict[str, Any]]], cap: int) -> List[Dict[str, Any]]:
    """Reciprocal Rank Fusion across pre-sorted chunk-dict lanes. Dedup by (type, id)."""
    scores: Dict[Tuple[str, str], float] = {}
    first: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for lane in lanes:
        for rank, ch in enumerate(lane, 1):
            key = (ch["content_type"], ch["id"])
            scores[key] = scores.get(key, 0.0) + 1.0 / (_RRF_K + rank)
            if key not in first:
                first[key] = ch
    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [first[key] for key, _ in ordered[:cap]]


def _format_grounding_context(
    book_dicts: List[Dict[str, Any]], ca_dicts: List[Dict[str, Any]]
) -> str:
    """Render retrieved chunks into an LLM-injectable markdown block."""
    lines: List[str] = []
    if book_dicts:
        lines.append("## Knowledge Base — Relevant Theory (retrieved)")
        for i, c in enumerate(book_dicts, 1):
            label = c["topic"] or "Topic"
            if c["subject"]:
                label += f" — {c['subject']}"
            lines.append(f"### [{i}] {label}  (relevance {c['score']:.2f})")
            lines.append(c["text"])
            lines.append("")
    if ca_dicts:
        lines.append("## Current Affairs — Related Developments (retrieved)")
        for i, c in enumerate(ca_dicts, 1):
            label = c["topic"] or "News"
            src = c.get("subject") or ""
            date = c.get("date") or ""
            head = f"### [CA{i}] {label}"
            if src or date:
                sep = ", " if src and date else ""
                head += f"  ({src}{sep}{date})"
            lines.append(head)
            lines.append(c["text"])
            lines.append("")
    return "\n".join(lines).strip()


def retrieve_grounding(
    query: Optional[str] = None,
    seed_topic_id: Optional[Any] = None,
    k_book: int = K_BOOK_DEFAULT,
    k_ca: int = K_CA_DEFAULT,
    db_alias: str = "default",
    ca_recency_days: Optional[int] = None,
) -> Dict[str, Any]:
    """
    THE grounding gateway. Retrieve cross-subject theory + recency chunks for a topic.

    Args:
        query:           Optional explicit query text. Combined with the seed topic's
                         own name/description/keywords to form the retrieval query.
        seed_topic_id:   knowledge.Topic UUID — the seed for graph expansion + query.
        k_book:          Max theory (book_chunk) chunks to return.
        k_ca:            Max recency (ca_chunk) chunks to return.
        db_alias:        'default' (== Supabase on Render) or 'supabase'.
        ca_recency_days: Optional recency window for CA chunks (None = no filter).

    Returns a GroundingResult dict:
        {query, chunks, book_chunks, ca_chunks, provenance, context_text, stats}
    Never raises — on any failure returns an empty result (caller falls back to wiki).
    """
    empty: Dict[str, Any] = {
        "query": "",
        "chunks": [],
        "book_chunks": [],
        "ca_chunks": [],
        "provenance": [],
        "context_text": "",
        "stats": {"book_hits": 0, "ca_hits": 0, "graph_topics": 0, "returned": 0},
    }
    try:
        from engines.knowledge.models import Topic

        seed_topic = None
        if seed_topic_id:
            seed_topic = (
                Topic.objects.using(db_alias)
                .filter(id=seed_topic_id)
                .select_related("subject")
                .first()
            )

        query_text = _build_seed_query(seed_topic, query)
        if not query_text:
            logger.warning(
                "grounding_empty_query",
                seed_topic_id=str(seed_topic_id) if seed_topic_id else None,
            )
            return empty

        query_vector = _grounding_query_embedding(query_text)
        if not query_vector:
            logger.warning("grounding_embed_failed", query=query_text[:80])
            return {**empty, "query": query_text}

        # ── Lane 1: global semantic book chunks (theory, unscoped across subjects) ──
        book_scored = _semantic_book_chunks(
            query_vector, db_alias, k_book * _CANDIDATE_MULTIPLIER
        )
        book_dicts = _fetch_book_chunk_dicts(book_scored, db_alias)

        # ── Lane 2: graph-expanded book chunks (TopicRelation neighbours, still gated) ──
        graph_topic_ids = (
            _graph_related_topic_ids(seed_topic_id, db_alias) if seed_topic_id else []
        )
        graph_dicts: List[Dict[str, Any]] = []
        if graph_topic_ids:
            graph_scored = _semantic_book_chunks(
                query_vector, db_alias, k_book, restrict_topic_ids=graph_topic_ids
            )
            graph_dicts = _fetch_book_chunk_dicts(graph_scored, db_alias)

        book_final = _rrf_merge([book_dicts, graph_dicts], cap=k_book)

        # ── Lane 3: semantic CA chunks (recency layer) ──
        ca_scored = _semantic_ca_chunks(query_vector, db_alias, k_ca)
        ca_dicts = _fetch_ca_chunk_dicts(
            ca_scored, db_alias, k_ca, recency_days=ca_recency_days
        )

        chunks = book_final + ca_dicts
        provenance = [
            {
                "content_type": c["content_type"],
                "id": c["id"],
                "topic": c["topic"],
                "subject": c["subject"],
                "score": c["score"],
            }
            for c in chunks
        ]
        context_text = _format_grounding_context(book_final, ca_dicts)

        logger.info(
            "grounding_complete",
            query=query_text[:80],
            book=len(book_final),
            ca=len(ca_dicts),
            graph_topics=len(graph_topic_ids),
            returned=len(chunks),
        )
        return {
            "query": query_text,
            "chunks": chunks,
            "book_chunks": book_final,
            "ca_chunks": ca_dicts,
            "provenance": provenance,
            "context_text": context_text,
            "stats": {
                "book_hits": len(book_dicts),
                "ca_hits": len(ca_dicts),
                "graph_topics": len(graph_topic_ids),
                "returned": len(chunks),
            },
        }

    except Exception as e:
        logger.error(
            "grounding_failed",
            error=str(e),
            seed_topic_id=str(seed_topic_id) if seed_topic_id else None,
        )
        sentry_sdk.capture_exception(e)
        return empty


# ── Slot adapters — render a GroundingResult into each prompt slot's exact shape ──
# These keep the existing prompt builders byte-for-byte unchanged.


def as_static_facts(result: Dict[str, Any], title: str = "") -> Dict[str, Any]:
    """
    Shape for daily_ca prompt_builder._format_static_facts():
        {title, key_provisions[], key_facts[], statistics[]}
    Built from retrieved book_chunk text (semantic) — replaces the old exact-topic regex.
    """
    import re

    book = result.get("book_chunks", [])
    texts = [c.get("text", "") for c in book]
    blob = "\n".join(texts)

    key_facts = [t[:300] for t in texts][:6]

    prov_pat = re.compile(
        r"[^.]*\b(?:Article|Section)\s+\d+[\w()]*[^.]*\.", re.IGNORECASE
    )
    key_provisions: List[str] = []
    seen_p: set = set()
    for m in prov_pat.finditer(blob):
        s = m.group(0).strip()[:250]
        if len(s) > 20 and s not in seen_p:
            key_provisions.append(s)
            seen_p.add(s)
        if len(key_provisions) >= 5:
            break

    stat_pat = re.compile(
        r"(?:₹|Rs\.?\s*|USD?\s*|\$)\s?\d[\d,]*(?:\.\d+)?\s*(?:crore|lakh|billion|million)?"
        r"|\b\d+(?:\.\d+)?\s*(?:%|percent)\b",
        re.IGNORECASE,
    )
    statistics: List[str] = []
    seen_s: set = set()
    for m in stat_pat.finditer(blob):
        v = m.group(0).strip()
        if v and v not in seen_s:
            statistics.append(v)
            seen_s.add(v)
        if len(statistics) >= 8:
            break

    return {
        "title": title or result.get("query", ""),
        "key_provisions": key_provisions,
        "key_facts": key_facts,
        "statistics": statistics,
    }


def as_wiki_enrichment(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Shape for daily_quiz prompt_builder._format_wiki_context():
        {intro, key_facts[], related_terms[], wiki_url}
    Built from retrieved chunks — replaces the wiki-only conceptual background.
    """
    book = result.get("book_chunks", [])
    ca = result.get("ca_chunks", [])

    intro = ""
    if book:
        intro = book[0].get("text", "")[:600]
    elif ca:
        intro = ca[0].get("text", "")[:600]

    key_facts = [c.get("text", "")[:240] for c in book[1:6]]
    if not key_facts:
        key_facts = [c.get("text", "")[:240] for c in ca[:5]]

    related: List[str] = []
    seen: set = set()
    for c in book:
        t = c.get("topic")
        if t and t not in seen:
            related.append(t)
            seen.add(t)
        if len(related) >= 5:
            break

    return {
        "intro": intro,
        "key_facts": key_facts,
        "related_terms": related,
        "wiki_url": "",
    }
