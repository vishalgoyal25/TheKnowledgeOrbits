"""
engines/book_content/services/ingestor_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The Master Orchestrator — runs the full 3-Layer pipeline for one topic.

Pipeline:
  Step 1-2 — Mode A only (wiki_only): no PDF extraction needed
  Step 3   — Hierarchy Classification (LLM Call #1 or map lookup)
  Step 4   — Subtopic Discovery (LLM Call #2)
  Step 5   — Wikipedia Full-Page Fetch (per subtopic)
  Step 6   — NCERT Section Extract (Mode B only — skipped for now)
  Step 7   — Quality Article Generation (Layer 2 Quality Engine)
  Step 8   — Sub-Subtopic Discovery + Articles (for [DEEP] subtopics)
  Step 9   — Coherence Pass (Layer 3)

Smart Skip: if BookContent already exists for a subtopic → skip LLM,
            still update concept registry (crash-safe resumption).

Ported from: upsc-agent-lab/src/ingestor.py
Changes: logging (structlog), imports, ALL DB ops replaced with Django ORM,
         pdf_path removed (wiki_only for now), topic_overview prompt PRESERVED,
         _generate_subtopic_article() REPLACED by generate_quality_article().
Preserved exactly: topic_overview prompt, smart skip logic, pipeline order,
                   all step comments, coherence pass call, generation log.
"""

import time
from typing import Optional
from urllib.parse import quote as url_quote

import requests
import sentry_sdk
import structlog
from django.db import transaction

from engines.book_content.models import BookContent, ContentMedia, GenerationLog
from engines.knowledge.models import Module, Subject, Topic

from .book_planner_service import (
    get_previously_covered_concepts,
    update_concept_registry,
)
from .classifier_service import classify_hierarchy
from .coherence_service import run_coherence_pass
from .llm_service import llm_call
from .quality_engine_service import generate_quality_article
from .subtopic_service import find_sub_subtopics, find_subtopics
from .wiki_service import extract_relevant_section, fetch_full_page

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════


def ingest_topic(
    topic_name: Optional[str] = None, subject_name: Optional[str] = None
) -> dict:
    """
    Master Agent Entry Point.

    Call with:
      ingest_topic(topic_name="Parliament of India")
      ingest_topic(topic_name="Parliament of India", subject_name="Indian Constitution & Polity")

    Returns:
      {"nodes_created": int, "relations_created": int, "topic": str}
    """
    _separator()
    logger.info("ingestor_start", topic_name=topic_name, subject_name=subject_name)
    _separator()

    # ── Steps 1 & 2: Mode A — wiki_only, no PDF ───────────────────────────────
    clean_ncert_text = ""  # Future Mode B: NCERT PDF extraction goes here
    logger.info("ingestor_mode", mode="A (Wikipedia only)")

    nodes_created = 0
    relations_created = 0
    start_time = time.time()

    try:
        # ── Step 3: Hierarchy Classification ─────────────────────────────────
        logger.info("ingestor_step3_classify", topic_name=topic_name)
        hierarchy = classify_hierarchy(
            topic_name=topic_name,
            ncert_text=clean_ncert_text[:1500] if clean_ncert_text else None,
        )
        subject = hierarchy["subject"]
        module = hierarchy["module"]
        topic = hierarchy["confirmed_topic"]

        # ── Step 4: Subtopic Discovery ────────────────────────────────────────
        logger.info("ingestor_step4_subtopics", topic=topic)
        subtopics = find_subtopics(topic, ncert_text=clean_ncert_text or None)

        if not subtopics:
            logger.warning("ingestor_no_subtopics_found", topic=topic)

        # ── Resolve / create knowledge hierarchy nodes ────────────────────────
        subject_obj = _get_or_create_subject(subject)
        module_obj = _get_or_create_module(module, subject_obj)
        topic_obj = _get_or_create_topic(
            topic, module_obj, subject_obj, node_type="topic"
        )

        # Generate topic overview and save to BookContent
        topic_wiki = fetch_full_page(topic)
        topic_overview = _generate_topic_overview(
            topic, clean_ncert_text, topic_wiki["summary"]
        )

        with transaction.atomic():
            topic_bc_obj, _ = BookContent.objects.update_or_create(
                topic=topic_obj,
                defaults={
                    "subject": subject_obj,
                    "content_markdown": topic_overview,
                    "word_count": len(topic_overview.split()),
                    "quality_score": 75.0,  # Fixed high score for intro overviews
                    "source_mode": "wiki_only",
                    "is_published": False,
                },
            )
            # Mark topic as generating
            Topic.objects.filter(id=topic_obj.id).update(content_status="generating")

        # Chunk + embed outside transaction so failures don't roll back the save
        _create_chunks_and_embeddings(topic_bc_obj)
        # Cross-link: Book↔CA and Book↔Book inter-subject (needs book_article embedding)
        _cross_link_to_ca(topic_bc_obj)
        _cross_link_inter_subject(topic_bc_obj)
        # G4: Fetch Wikipedia hero image → re-host on Cloudinary → save ContentMedia
        _fetch_and_store_hero_image(topic_bc_obj)

        nodes_created += 1
        logger.info("ingestor_topic_overview_saved", topic=topic)

        # ── Steps 5-8: Process each subtopic ─────────────────────────────────
        for i, sub in enumerate(subtopics, 1):
            sub_name = sub["name"]
            needs_deep = sub["needs_deep"]

            logger.info(
                "ingestor_subtopic_start",
                index=i,
                total=len(subtopics),
                subtopic=sub_name,
                needs_deep=needs_deep,
            )

            # ── Smart Skip: check if BookContent already exists ───────────────
            existing = BookContent.objects.filter(topic__name=sub_name).first()
            if existing:
                logger.info(
                    "ingestor_smart_skip", subtopic=sub_name, reason="already_exists"
                )
                # SYNCED SKIPPING: still register in concept registry
                update_concept_registry(
                    subject, sub_name, str(existing.topic.id), sub_name
                )
                sub_topic_obj = existing.topic
            else:
                # Step 5: Fetch Wikipedia for subtopic
                logger.info("ingestor_step5_wiki", subtopic=sub_name)
                wiki_data = fetch_full_page(sub_name)
                wiki_section = extract_relevant_section(wiki_data["content"], sub_name)[
                    :3000
                ]

                # Step 6: NCERT section (Mode B — skipped, no PDF for now)
                ncert_section = ""

                # Step 7: Generate quality article (Layer 2)
                logger.info("ingestor_step7_generate", subtopic=sub_name)
                previously_covered = get_previously_covered_concepts(subject, sub_name)
                article_md, quality_score = generate_quality_article(
                    subtopic=sub_name,
                    parent_topic=topic,
                    ncert_section=ncert_section,
                    wiki_content=wiki_section,
                    previously_covered=previously_covered,
                    subject=subject,
                )

                # Save subtopic node + BookContent
                sub_topic_obj = _get_or_create_topic(
                    sub_name,
                    module_obj,
                    subject_obj,
                    node_type="subtopic",
                    parent_topic=topic_obj,
                )

                with transaction.atomic():
                    sub_bc_obj, _ = BookContent.objects.update_or_create(
                        topic=sub_topic_obj,
                        defaults={
                            "subject": subject_obj,
                            "content_markdown": article_md,
                            "word_count": len(article_md.split()),
                            "quality_score": quality_score,
                            "source_mode": "wiki_only",
                            "is_published": False,
                        },
                    )
                    Topic.objects.filter(id=sub_topic_obj.id).update(
                        content_status="book_quality"
                    )

                # Chunk + embed outside transaction so failures don't roll back the save
                _create_chunks_and_embeddings(sub_bc_obj)
                _cross_link_to_ca(sub_bc_obj)
                _cross_link_inter_subject(sub_bc_obj)
                # G4: Fetch Wikipedia hero image → re-host on Cloudinary → save ContentMedia
                _fetch_and_store_hero_image(sub_bc_obj)

                # Register in concept registry
                update_concept_registry(
                    subject, sub_name, str(sub_topic_obj.id), sub_name
                )

                _log_generation(
                    topic_name=sub_name,
                    subject_name=subject,
                    status="success",
                    nodes_created=1,
                    quality_score=quality_score,
                    word_count=len(article_md.split()),
                    start_time=start_time,
                )

                nodes_created += 1
                relations_created += 1
                logger.info(
                    "ingestor_subtopic_saved",
                    subtopic=sub_name,
                    quality_score=quality_score,
                    words=len(article_md.split()),
                )

            # ── Step 8: Recursive deep expansion ─────────────────────────────
            if needs_deep:
                logger.info("ingestor_step8_deep_expand", subtopic=sub_name)
                sub_subtopics = find_sub_subtopics(sub_name, topic)

                for ss_name in sub_subtopics:
                    logger.info("ingestor_sub_subtopic_start", name=ss_name)

                    # Smart Skip for sub-subtopics
                    existing_ss = BookContent.objects.filter(
                        topic__name=ss_name
                    ).first()
                    if existing_ss:
                        logger.info(
                            "ingestor_smart_skip",
                            subtopic=ss_name,
                            reason="already_exists",
                        )
                        update_concept_registry(
                            subject, ss_name, str(existing_ss.topic.id), ss_name
                        )
                        continue

                    ss_wiki = fetch_full_page(ss_name)
                    ss_section = extract_relevant_section(ss_wiki["content"], ss_name)[
                        :3000
                    ]
                    ss_ncert = ""  # Mode B: would extract from NCERT here

                    logger.info("ingestor_step7_generate", subtopic=ss_name)
                    previously_covered = get_previously_covered_concepts(
                        subject, ss_name
                    )
                    ss_article, ss_quality = generate_quality_article(
                        subtopic=ss_name,
                        parent_topic=sub_name,
                        ncert_section=ss_ncert,
                        wiki_content=ss_section,
                        previously_covered=previously_covered,
                        subject=subject,
                    )

                    ss_topic_obj = _get_or_create_topic(
                        ss_name,
                        module_obj,
                        subject_obj,
                        node_type="sub_subtopic",
                        parent_topic=sub_topic_obj,
                    )

                    with transaction.atomic():
                        ss_bc_obj, _ = BookContent.objects.update_or_create(
                            topic=ss_topic_obj,
                            defaults={
                                "subject": subject_obj,
                                "content_markdown": ss_article,
                                "word_count": len(ss_article.split()),
                                "quality_score": ss_quality,
                                "source_mode": "wiki_only",
                                "is_published": False,
                            },
                        )
                        Topic.objects.filter(id=ss_topic_obj.id).update(
                            content_status="book_quality"
                        )

                    # Chunk + embed outside transaction so failures don't roll back the save
                    _create_chunks_and_embeddings(ss_bc_obj)
                    _cross_link_to_ca(ss_bc_obj)
                    _cross_link_inter_subject(ss_bc_obj)
                    # G4: Fetch Wikipedia hero image → re-host on Cloudinary → save ContentMedia
                    _fetch_and_store_hero_image(ss_bc_obj)

                    update_concept_registry(
                        subject, ss_name, str(ss_topic_obj.id), ss_name
                    )

                    _log_generation(
                        topic_name=ss_name,
                        subject_name=subject,
                        status="success",
                        nodes_created=1,
                        quality_score=ss_quality,
                        word_count=len(ss_article.split()),
                        start_time=start_time,
                    )

                    nodes_created += 1
                    relations_created += 1
                    logger.info(
                        "ingestor_sub_subtopic_saved",
                        name=ss_name,
                        quality_score=ss_quality,
                        words=len(ss_article.split()),
                    )

        # ── Step 9: Coherence Pass (Layer 3) ─────────────────────────────────
        logger.info("ingestor_step9_coherence", topic=topic)
        run_coherence_pass(str(topic_obj.id), topic, subject)

        # Mark parent topic as book_quality
        Topic.objects.filter(id=topic_obj.id).update(content_status="book_quality")

        # Final generation log
        elapsed = int(time.time() - start_time)
        _log_generation(
            topic_name=topic,
            subject_name=subject,
            status="success",
            nodes_created=nodes_created,
            relations_created=relations_created,
            quality_score=0.0,
            word_count=0,
            start_time=start_time,
        )

    except Exception as e:
        elapsed = int(time.time() - start_time)
        logger.error("ingestor_failed", topic_name=topic_name, error=str(e))
        sentry_sdk.capture_exception(e)
        try:
            GenerationLog.objects.create(
                topic_name=topic_name or "",
                subject_name=subject_name or "",
                status="failed",
                error_message=str(e),
                generation_time_seconds=elapsed,
            )
        except Exception:
            pass
        raise

    _separator()
    logger.info(
        "ingestor_complete",
        topic=topic,
        nodes_created=nodes_created,
        relations_created=relations_created,
    )
    _separator()

    return {
        "nodes_created": nodes_created,
        "relations_created": relations_created,
        "topic": topic,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TOPIC OVERVIEW GENERATION (prompt preserved exactly from POC)
# ═══════════════════════════════════════════════════════════════════════════════


def _generate_topic_overview(topic: str, ncert_text: str, wiki_summary: str) -> str:
    """
    Generates a concise topic-level overview article (~400 words).
    This is the intro node that readers see before drilling into subtopics.
    """
    if ncert_text:
        prompt = f"""You are writing an overview introduction for a UPSC study book chapter.

TOPIC: "{topic}"

NCERT CHAPTER CONTEXT (first section):
{ncert_text[:3000]}

WIKIPEDIA SUMMARY:
{wiki_summary[:500]}

Write a concise, engaging OVERVIEW for "{topic}" (~400 words).
  - What this topic is and why it matters for UPSC
  - Key constitutional/legal foundation (1-2 sentences)
  - What subtopics this chapter covers (as a list)
  - Exam relevance (Prelims/Mains)

Use Markdown. Start with: ## {topic}"""
    else:
        prompt = f"""You are writing an overview introduction for a UPSC study book chapter.

TOPIC: "{topic}"

WIKIPEDIA SUMMARY:
{wiki_summary[:800]}

Write a concise, engaging OVERVIEW for "{topic}" (~400 words).
  - What this topic is and why it matters for UPSC
  - Key constitutional/legal foundation (1-2 sentences)
  - What subtopics this chapter covers (as a list)
  - Exam relevance (Prelims/Mains)

Use Markdown. Start with: ## {topic}"""

    result = llm_call(prompt, mode="standard")
    return result or f"## {topic}\n\nOverview coming soon."


# ═══════════════════════════════════════════════════════════════════════════════
# DJANGO ORM HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


def _get_or_create_subject(subject_name: str) -> Subject:
    """
    Gets or creates a Subject by name.
    Safe to re-run — never creates duplicates.
    """
    from engines.knowledge.models import Program

    program, _ = Program.objects.get_or_create(
        name="UPSC CSE", defaults={"description": "UPSC Civil Services Examination"}
    )
    subject, created = Subject.objects.get_or_create(
        name=subject_name,
        program=program,
        defaults={"description": f"UPSC subject: {subject_name}", "is_active": True},
    )
    if created:
        logger.info("subject_created", name=subject_name)
    else:
        logger.info("subject_reused", name=subject_name)
    return subject


def _get_or_create_module(module_name: str, subject: Subject) -> Module:
    """
    Gets or creates a Module by name under a subject.
    Safe to re-run — never creates duplicates.
    """
    module, created = Module.objects.get_or_create(
        name=module_name,
        subject=subject,
        defaults={"description": f"Module: {module_name}", "is_active": True},
    )
    if created:
        logger.info("module_created", name=module_name, subject=subject.name)
    else:
        logger.info("module_reused", name=module_name)
    return module


def _get_or_create_topic(
    topic_name: str,
    module: Module,
    subject: Subject,
    node_type: str = "topic",
    parent_topic: Optional[Topic] = None,
) -> Topic:
    """
    Gets or creates a Topic node in knowledge_topic.
    node_type drives the hierarchy depth:
      'topic'        → level 3 (main topic)
      'subtopic'     → level 4 (subtopic under topic)
      'sub_subtopic' → level 5 (sub-subtopic under subtopic)
    Safe to re-run — never creates duplicates.
    """
    topic, created = Topic.objects.get_or_create(
        name=topic_name,
        module=module,
        defaults={
            "subject": subject,
            "parent_topic": parent_topic,
            "topic_type": "syllabus",
            "is_active": True,
        },
    )
    if created:
        # Set node_type via update (column added via RunSQL migration)
        Topic.objects.filter(id=topic.id).update(node_type=node_type)
        logger.info("topic_created", name=topic_name, node_type=node_type)
    else:
        logger.info("topic_reused", name=topic_name)
    return topic


def _log_generation(
    topic_name: str,
    subject_name: str,
    status: str,
    nodes_created: int = 0,
    relations_created: int = 0,
    quality_score: float = 0.0,
    word_count: int = 0,
    error_message: str = "",
    start_time: float = 0.0,
) -> None:
    """Creates a GenerationLog entry for crash recovery and admin monitoring."""
    try:
        elapsed = int(time.time() - start_time) if start_time else 0
        GenerationLog.objects.create(
            topic_name=topic_name,
            subject_name=subject_name,
            status=status,
            nodes_created=nodes_created,
            relations_created=relations_created,
            quality_score=quality_score,
            word_count=word_count,
            error_message=error_message,
            generation_time_seconds=elapsed,
        )
    except Exception as e:
        logger.warning("generation_log_failed", error=str(e))
        sentry_sdk.capture_exception(e)


# ═══════════════════════════════════════════════════════════════════════════════
# CHUNK + EMBEDDING PIPELINE (Phase E)
# ═══════════════════════════════════════════════════════════════════════════════


def _create_chunks_and_embeddings(book_content_obj: BookContent) -> None:
    """
    Full chunking + embedding pipeline for one BookContent article.

    Called after every BookContent.update_or_create(). Idempotent — existing
    chunks/embeddings for this article are deleted before re-creating.

    Pipeline:
      1. Split article markdown into ~1200-char semantic chunks (ChunkingService)
      2. Bulk-create BookChunk rows
      3. Populate search_vector (tsvector) for BM25 keyword search
      4. Batch-generate 384-dim embeddings for all chunks (EmbeddingService)
      5. Bulk-create content_embedding rows (content_type='book_chunk') for RAG
      6. Generate article-level embedding (content_type='book_article') for similarity

    Never raises — logs error + captures to Sentry so the ingestion pipeline
    continues even if chunking/embedding fails for one article.
    """
    try:
        # ── Lazy imports: avoid circular imports + heavy ML load at module level ──
        from django.contrib.postgres.search import SearchVector

        from engines.book_content.models import BookChunk
        from engines.content.models import Embedding
        from engines.content.services.chunking_service import ChunkingService
        from engines.content.services.embedding_service import EmbeddingService

        topic_name: str = (
            book_content_obj.topic.name if book_content_obj.topic_id else "unknown"
        )
        article_text: str = book_content_obj.content_markdown or ""

        if not article_text.strip():
            logger.warning("chunk_pipeline_skip_empty", topic=topic_name)
            return

        logger.info(
            "chunk_pipeline_start", topic=topic_name, text_len=len(article_text)
        )

        # ── Step 1: Chunk the article markdown ───────────────────────────────
        chunk_dicts = ChunkingService.chunk_text(
            text=article_text,
            document_id=str(book_content_obj.id),
            page_number=0,
            chapter_name=topic_name,
        )

        if not chunk_dicts:
            logger.warning("chunk_pipeline_no_chunks", topic=topic_name)
            return

        # ── Step 2: Delete stale chunks + their embeddings (idempotent) ──────
        old_chunk_ids = list(
            BookChunk.objects.filter(book_content=book_content_obj).values_list(
                "id", flat=True
            )
        )
        if old_chunk_ids:
            Embedding.objects.filter(
                content_type="book_chunk",
                content_id__in=old_chunk_ids,
            ).delete()
            BookChunk.objects.filter(book_content=book_content_obj).delete()
            logger.info(
                "chunk_pipeline_stale_deleted",
                count=len(old_chunk_ids),
                topic=topic_name,
            )

        # ── Step 3: Bulk-create BookChunk rows ───────────────────────────────
        book_chunks = BookChunk.objects.bulk_create(
            [
                BookChunk(
                    book_content=book_content_obj,
                    chunk_text=cd["chunk_text"],
                    chunk_index=cd["chunk_index"],
                    source_type="wiki",  # Mode A: all sources are Wikipedia
                    quality_flag=cd.get("quality_flag", "high"),
                )
                for cd in chunk_dicts
            ]
        )
        logger.info(
            "chunk_pipeline_chunks_created", count=len(book_chunks), topic=topic_name
        )

        # ── Step 4: Populate search_vector (BM25 / tsvector) ─────────────────
        # Single bulk UPDATE — generates tsvector for all chunks in one SQL call
        BookChunk.objects.filter(book_content=book_content_obj).update(
            search_vector=SearchVector("chunk_text", config="english")
        )
        logger.info("chunk_pipeline_search_vector_updated", topic=topic_name)

        # ── Step 5: Batch-generate chunk embeddings ───────────────────────────
        # One HTTP call to HF API for all chunk texts — efficient
        chunk_texts = [cd["chunk_text"] for cd in chunk_dicts]
        chunk_vectors = EmbeddingService.generate_embeddings_batch(chunk_texts)

        # Fetch saved chunks ordered by chunk_index to align with chunk_vectors
        saved_chunks = list(
            BookChunk.objects.filter(book_content=book_content_obj).order_by(
                "chunk_index"
            )
        )

        # ── Step 6: Bulk-create chunk embeddings ─────────────────────────────
        chunk_embeddings = Embedding.objects.bulk_create(
            [
                Embedding(
                    content_type="book_chunk",
                    content_id=chunk.id,
                    vector=chunk_vectors[i],
                    model_name=EmbeddingService.MODEL_NAME,
                )
                for i, chunk in enumerate(saved_chunks)
                if i < len(chunk_vectors) and chunk_vectors[i]
            ],
            ignore_conflicts=True,
        )
        logger.info(
            "chunk_pipeline_chunk_embeddings_created",
            count=len(chunk_embeddings),
            topic=topic_name,
        )

        # ── Step 7: Article-level embedding (fast similarity search) ─────────
        # Use first 1200 chars as summary proxy — stays within model token limit
        article_summary = article_text[:1200]
        article_vector = EmbeddingService.generate_embedding(article_summary)

        Embedding.objects.update_or_create(
            content_type="book_article",
            content_id=book_content_obj.id,
            defaults={
                "vector": article_vector,
                "model_name": EmbeddingService.MODEL_NAME,
            },
        )
        logger.info("chunk_pipeline_article_embedding_saved", topic=topic_name)

        logger.info(
            "chunk_pipeline_complete",
            topic=topic_name,
            chunks=len(book_chunks),
            chunk_embeddings=len(chunk_embeddings),
            article_embedding=1,
        )

    except Exception as e:
        logger.error(
            "chunk_pipeline_failed",
            topic=getattr(book_content_obj.topic, "name", "unknown"),
            error=str(e),
        )
        sentry_sdk.capture_exception(e)
        # DO NOT re-raise — chunking failure must never abort the ingestion pipeline


def _cross_link_to_ca(book_content_obj: BookContent) -> None:
    """
    Wrapper: create persistent CA↔Book TopicRelation(cross_subject) records.
    Called after _create_chunks_and_embeddings (book_article embedding must exist).
    Never raises — failure must not abort ingestion.
    """
    try:
        from engines.book_content.services.retrieval_service import (
            create_cross_links_for_book_article,
        )

        links = create_cross_links_for_book_article(book_content_obj)
        logger.info(
            "ingestor_ca_cross_links",
            topic=getattr(book_content_obj.topic, "name", "unknown"),
            links=links,
        )
    except Exception as e:
        logger.warning("ingestor_ca_cross_link_failed", error=str(e))
        sentry_sdk.capture_exception(e)


def _cross_link_inter_subject(book_content_obj: BookContent) -> None:
    """
    Wrapper: create Book↔Book cross-subject TopicRelation edges.
    e.g. "Budget" (Economy) ──cross_subject──▶ "Budget Process" (Polity).
    Called after _cross_link_to_ca so book_article embedding already exists.
    Never raises — failure must not abort ingestion.
    """
    try:
        from engines.book_content.services.retrieval_service import (
            create_book_inter_subject_links,
        )

        links = create_book_inter_subject_links(book_content_obj)
        logger.info(
            "ingestor_inter_subject_links",
            topic=getattr(book_content_obj.topic, "name", "unknown"),
            links=links,
        )
    except Exception as e:
        logger.warning("ingestor_inter_subject_link_failed", error=str(e))
        sentry_sdk.capture_exception(e)


# ═══════════════════════════════════════════════════════════════════════════════
# G4 — WIKIPEDIA HERO IMAGE → CLOUDINARY  (auto image pipeline)
# ═══════════════════════════════════════════════════════════════════════════════

_WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
_WIKI_HEADERS = {
    "User-Agent": "TheKnowledgeOrbits/1.0 (contact@theknowledgeorbits.com)"
}


def _cld_slug(name: str, max_len: int = 40) -> str:
    """
    Convert a human name into a Cloudinary-safe folder segment.
    Rules: lowercase, spaces → underscores, drop all non-alphanumeric/underscore chars,
    collapse multiple underscores, truncate to max_len.

    Examples:
      "Indian Constitution & Polity" → "indian_constitution_and_polity"
      "Fundamental Rights (Part III)" → "fundamental_rights_part_iii"
    """
    import re

    s = name.lower()
    s = s.replace("&", "and")
    s = re.sub(r"[^a-z0-9\s]", " ", s)  # non-alphanumeric → space
    s = re.sub(r"\s+", "_", s.strip())  # spaces → underscores
    s = re.sub(r"_+", "_", s)  # collapse repeated underscores
    return s[:max_len].rstrip("_")


def _fetch_and_store_hero_image(book_content_obj: BookContent) -> None:
    """
    Fetch the Wikipedia page summary hero image, re-host on Cloudinary in a
    structured folder hierarchy, tag with all IDs, and save to ContentMedia.

    Cloudinary folder layout:
      tko/upsc/{subject_slug}/{module_slug}/

    Cloudinary public_id (filename, within folder):
      {topic_uuid}_hero

    Full example path on Cloudinary:
      tko/upsc/indian_constitution_and_polity/fundamental_rights/{uuid}_hero

    This guarantees:
      ✓ Zero collision   — topic UUID is mathematically unique
      ✓ Idempotent       — overwrite=True replaces old image on re-generation
      ✓ Neat hierarchy   — browsable per subject → module in Cloudinary dashboard
      ✓ Searchable tags  — filter by subject_id / topic_id in Cloudinary Media Library
      ✓ Rich metadata    — full context (IDs + names) visible on each asset

    Filter rules (skip bad images):
      - No `originalimage` key in the Wikipedia response
      - width < 200px (icons, flags, tiny thumbnails)
      - URL ends in .svg (vector diagrams — unsupported by <Image>)

    Completely non-blocking: wrapped in try/except. Any failure is logged +
    sent to Sentry but NEVER raises. Image failure must not abort article generation.
    """
    try:
        import cloudinary
        import cloudinary.uploader
        from django.conf import settings

        # ── Extract hierarchy metadata from book_content_obj ─────────────────
        # All IDs and names are derived here — no extra arguments needed.
        topic_obj = book_content_obj.topic  # FK — may query DB once
        subject_obj = book_content_obj.subject  # FK — may query DB once
        module_obj = topic_obj.module  # FK — may query DB once

        topic_id: str = str(topic_obj.id)
        topic_name: str = topic_obj.name
        node_type: str = getattr(topic_obj, "node_type", "topic")

        subject_id: str = str(subject_obj.id)
        subject_name: str = subject_obj.name

        module_id: str = str(module_obj.id)
        module_name: str = module_obj.name

        # ── Step 1: Fetch Wikipedia page summary ─────────────────────────────
        encoded_topic = url_quote(topic_name, safe="")
        api_url = _WIKI_SUMMARY_URL.format(encoded_topic)

        resp = requests.get(api_url, headers=_WIKI_HEADERS, timeout=10)
        if resp.status_code != 200:
            logger.info(
                "hero_image_wiki_skip",
                topic=topic_name,
                reason="non_200_response",
                status=resp.status_code,
            )
            return

        data = resp.json()

        # ── Filter: must have originalimage ──────────────────────────────────
        original = data.get("originalimage")
        if not original:
            logger.info(
                "hero_image_wiki_skip",
                topic=topic_name,
                reason="no_originalimage_key",
            )
            return

        image_url: str = original.get("source", "")
        image_width: int = original.get("width", 0)

        # ── Filter: skip icons and tiny thumbnails (< 200 px) ────────────────
        if image_width < 200:
            logger.info(
                "hero_image_wiki_skip",
                topic=topic_name,
                reason="width_too_small",
                width=image_width,
            )
            return

        # ── Filter: skip SVG vector files ─────────────────────────────────────
        if image_url.lower().endswith(".svg"):
            logger.info(
                "hero_image_wiki_skip",
                topic=topic_name,
                reason="svg_format",
                url=image_url,
            )
            return

        # ── Extract caption from Wikipedia description ────────────────────────
        wiki_description: str = data.get("description", "") or ""
        wiki_caption: str = wiki_description[:200] if wiki_description else topic_name

        # ── Step 2: Configure Cloudinary (safety net over auto-config) ───────
        cloudinary_settings = getattr(settings, "CLOUDINARY_STORAGE", {})
        if cloudinary_settings.get("CLOUD_NAME"):
            cloudinary.config(
                cloud_name=cloudinary_settings["CLOUD_NAME"],
                api_key=cloudinary_settings["API_KEY"],
                api_secret=cloudinary_settings["API_SECRET"],
            )

        # ── Build deterministic folder + public_id ────────────────────────────
        #
        # Folder:    tko/upsc/{subject_slug}/{module_slug}
        # Public ID: {topic_uuid}_hero
        #
        # With overwrite=True + explicit public_id, re-running the ingestor for
        # the same topic replaces the old image cleanly — no duplicate uploads.
        #
        subject_slug = _cld_slug(subject_name)
        module_slug = _cld_slug(module_name)
        folder = f"tko/upsc/{subject_slug}/{module_slug}"
        public_id = f"{topic_id}_hero"  # UUID → zero collision guaranteed

        # ── Step 3: Upload to Cloudinary (re-hosting from Wikimedia) ─────────
        upload_result = cloudinary.uploader.upload(
            image_url,
            folder=folder,
            public_id=public_id,
            resource_type="image",
            overwrite=True,  # idempotent: same topic → same slot
            use_filename=False,
            unique_filename=False,  # we control the filename via public_id
            # ── Searchable tags (filterable in Cloudinary Media Library) ───
            tags=[
                "tko",
                "upsc",
                f"subject_{subject_id}",
                f"module_{module_id}",
                f"topic_{topic_id}",
                node_type,
            ],
            # ── Rich context metadata (visible on each asset in dashboard) ──
            context=(
                f"topic_id={topic_id}"
                f"|topic_name={topic_name}"
                f"|subject_id={subject_id}"
                f"|subject_name={subject_name}"
                f"|module_id={module_id}"
                f"|module_name={module_name}"
                f"|node_type={node_type}"
            ),
        )

        cloudinary_url: str = upload_result.get("secure_url", "")
        if not cloudinary_url:
            logger.warning("hero_image_upload_no_url", topic=topic_name)
            return

        # ── Step 4: Save to ContentMedia (idempotent upsert) ─────────────────
        # Keyed on (content, media_type="image") so re-runs update rather than duplicate.
        ContentMedia.objects.update_or_create(
            content=book_content_obj,
            media_type="image",
            defaults={
                "cloudinary_url": cloudinary_url,
                "position": "hero",
                "position_marker": "",  # hero images have no inline marker
                "alt_text": topic_name,
                "caption": wiki_caption,
                "display_order": 0,
            },
        )

        logger.info(
            "hero_image_saved",
            topic=topic_name,
            topic_id=topic_id,
            subject=subject_name,
            module=module_name,
            folder=folder,
            cloudinary_url=cloudinary_url,
            original_width=image_width,
        )

    except Exception as e:
        topic_label = getattr(
            getattr(book_content_obj, "topic", None), "name", str(book_content_obj.pk)
        )
        logger.warning("hero_image_failed", topic=topic_label, error=str(e))
        sentry_sdk.capture_exception(e)
        # Never re-raise — image failure must not abort article generation


def _separator():
    logger.info("ingestor_separator", line="━" * 55)
