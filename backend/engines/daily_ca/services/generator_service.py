"""
engines/daily_ca/services/generator_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase J3 — DailyCaGeneratorService
Phase D1 (FEATURES3) — Enriched CA context: combines chunk text + parent article content.

Main entry point: run_generation_cycle(proposals, groq_calls_used=0) → dict

Architecture: CA-First, Static-Background
  _run_single_cycle()       — generates ONE CA article (fast, ~15-20s)
                              never blocks, never waits for static
  run_generation_cycle()    — runs all cycles, collects topics needing static,
                              fires trigger_pending_static_generation() ONCE after all done

GROQ call budget per cycle:
  1 call  — main CA article generation (writer mode, high token limit)
  0-8     — new concept page stubs (1 per unknown [[term]], max 8)
  1 call  — keyword tag extraction (standard mode, only if overrides insufficient)
  ────
  ~2-10 calls per cycle typical. Session cap = 25 across all cycles.

Failed cycles do NOT stop the run — marked 'failed', loop continues.
Session cap hit → remaining proposals marked 'queued_next_run' → stop gracefully.

Phase D1 context enrichment:
  _fetch_enriched_ca_context() replaces _fetch_ca_chunks_text().
  Returns (enriched_text, chunk_word_count):
    enriched_text      — chunks + parent CAArticle.content combined (cap: 4000 chars)
    chunk_word_count   — words in chunks only (used for wiki enrichment threshold)
  This gives the LLM both: specific news relevance (chunks) + full factual depth
  of the original source article (names, dates, figures, quotes).
"""

import re
import time
from uuid import UUID

import sentry_sdk
import structlog
from django.db import transaction
from django.utils.text import slugify

from engines.book_content.services.llm_service import INTER_CALL_SLEEP, llm_call
from engines.daily_ca.models import CaDailyProposal, DailyCaArticle, DailyCaStaticLink
from engines.daily_ca.services.prompt_builder import (
    build_ca_prompt,
)
from engines.daily_ca.services.static_background_service import StaticBackgroundService
from engines.daily_ca.services.wiki_enrichment_service import WikiEnrichmentService
from engines.tags.services.concept_resolver import ConceptPageResolver
from engines.tags.services.tag_service import TagService

logger = structlog.get_logger(__name__)

# ── Quality scoring constants ─────────────────────────────────────────────────
_QUALITY_MIN_WORDS = 450
_QUALITY_MAX_WORDS = 800

# Phrases that indicate exam-note regression or filler writing — used in quality scorer
# and as a post-generation filter. Covers all four GS subject areas.
_FORBIDDEN_PHRASES = [
    # Exam-language (all subjects)
    "upsc",
    "gs1",
    "gs2",
    "gs3",
    "gs4",
    "mains value",
    "mains preparation",
    "prelims",
    "prelims focus",
    "important for exam",
    "this is important for",
    "civil services perspective",
    "from an exam standpoint",
    "aspirants should note",
    "important for competitive",
    # Filler openers (all subjects)
    "why in news",
    "it goes without saying",
    "it is pertinent to note",
    "in recent times",
    "in recent years",
    "against this backdrop",
    "in the wake of",
    "amid growing concerns",
    # Hedging filler (all subjects)
    "experts believe",
    "some analysts say",
    "it is widely acknowledged",
    "many feel that",
    "it is believed that",
]

# ── Response parsing patterns ─────────────────────────────────────────────────
_TAGS_LINE = re.compile(r"^TAGS:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
_SOURCE_LINE = re.compile(r"^SOURCE:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
_CATEGORY_LINE = re.compile(r"^CATEGORY:\s*(.+)$", re.MULTILINE | re.IGNORECASE)

_VALID_CATEGORIES = frozenset(
    {
        "national",
        "international",
        "geo-politics",
        "geo-economics",
        "economy",
        "science-tech",
        "environment",
        "society",
        "law-justice",
        "defence",
        "health",
        "sports-awards",
    }
)
# Title on its own line — either "# Title" or bold "**Title**" or plain first line
_TITLE_LINE = re.compile(r"^#+\s+(.+)$", re.MULTILINE)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _fetch_enriched_ca_context(
    ca_chunk_ids: list, db_alias: str = "default"
) -> tuple[str, int]:
    """
    Phase D1 — Fetches enriched CA context by combining two complementary sources:

      Layer 1 — CAChunk.chunk_text (pre-scored, most UPSC-relevant segments)
        These are short embedded segments (~100–300 words). They are the highest-
        signal material — already scored by RelevanceScorerService, topically focused.

      Layer 2 — Parent CAArticle.content (full scraped article text)
        The original newspaper article (The Hindu, Indian Express, PIB etc.).
        Contains named officials, specific dates, exact figures, direct quotes,
        and detailed context that chunks often omit.

    Why both layers matter:
      Chunks alone → LLM gets the UPSC angle but lacks factual specificity.
      Parent content → adds names, dates, rupee figures, official statements —
      exactly what makes articles feel authoritative rather than generic.

    Returns:
        (enriched_text, chunk_word_count) tuple where:
          enriched_text     — combined text capped at 4000 chars, structured with
                              clear section labels so LLM knows what each part is.
          chunk_word_count  — word count of chunks ONLY (not parent content).
                              Used by caller for wiki enrichment threshold check —
                              wiki is triggered only when chunks are thin (< 300 words),
                              independent of how much parent content is available.

    Failure modes:
      - Parent content fetch fails for a chunk → logged, skipped (best-effort)
      - All DB access fails → returns ("", 0), Sentry capture, never raises
    """
    if not ca_chunk_ids:
        return "", 0

    try:
        from engines.current_affairs.models import CAChunk

        chunks = list(
            CAChunk.objects.using(db_alias)
            .filter(id__in=ca_chunk_ids)
            .select_related("ca_article", "ca_article__source")
            .order_by("chunk_index")
        )

        chunk_texts: list[str] = []
        parent_content_parts: list[str] = []
        seen_article_ids: set = set()

        for chunk in chunks:
            # Layer 1: chunk text
            if chunk.chunk_text and chunk.chunk_text.strip():
                chunk_texts.append(chunk.chunk_text.strip())

            # Layer 2: parent article content — once per unique parent article
            try:
                ca_article = chunk.ca_article
                if ca_article and ca_article.id not in seen_article_ids:
                    seen_article_ids.add(ca_article.id)
                    content = (ca_article.content or "").strip()
                    if len(content) > 100:
                        source_name = (
                            ca_article.source.name
                            if ca_article.source
                            else "News Source"
                        )
                        # First 1000 chars captures headline + lead paragraphs
                        # where named details (officials, figures, dates) concentrate
                        parent_content_parts.append(
                            f"[Source: {source_name}]\n{content[:1000]}"
                        )
            except Exception:
                pass  # Parent fetch is best-effort — never block article generation

        # Compute chunk word count BEFORE building combined text
        # (used by caller for wiki enrichment threshold — must be chunk-only)
        chunk_word_count = sum(len(t.split()) for t in chunk_texts)

        # Build combined text with clear structural labels
        parts: list[str] = []
        if chunk_texts:
            parts.append(
                "KEY EXCERPTS (topically focused, highest-relevance segments):\n"
                + "\n\n".join(chunk_texts)
            )
        if parent_content_parts:
            parts.append(
                "FULL SOURCE ARTICLES (original news — specific names, dates, figures, quotes):\n"
                + "\n\n---\n\n".join(parent_content_parts)
            )

        if not parts:
            return "", 0

        combined = "\n\n".join(parts)

        logger.info(
            "generator_enriched_context_built",
            chunk_count=len(chunk_texts),
            parent_articles=len(parent_content_parts),
            chunk_words=chunk_word_count,
            total_chars=len(combined),
        )

        # Cap at 4000 chars — richer context window (up from 2000)
        return combined[:4000], chunk_word_count

    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logger.error(
            "generator_fetch_enriched_context_failed",
            error=str(exc)[:200],
        )
        return "", 0


def _parse_response(raw: str) -> tuple[str, str, list[str], str, str]:
    """
    Parses the LLM response into its five components.

    Returns:
        (title, body_md, tags_raw, source_attr, news_category)
        - title:         extracted title string
        - body_md:       article body without CATEGORY:/TAGS:/SOURCE: footer lines
        - tags_raw:      list of tag strings from TAGS: line
        - source_attr:   raw SOURCE: line value
        - news_category: validated category slug (default: "national")
    """
    if not raw:
        return ("Untitled", "", [], "", "national")

    text = raw.strip()

    # Extract and remove CATEGORY: line
    news_category = "national"
    cat_match = _CATEGORY_LINE.search(text)
    if cat_match:
        raw_cat = cat_match.group(1).strip().lower().replace(" ", "-")
        if raw_cat in _VALID_CATEGORIES:
            news_category = raw_cat
        text = text[: cat_match.start()].rstrip() + text[cat_match.end() :]

    # Extract and remove TAGS: line
    tags_raw: list[str] = []
    tags_match = _TAGS_LINE.search(text)
    if tags_match:
        raw_tags = tags_match.group(1)
        tags_raw = [t.strip().lower() for t in raw_tags.split(",") if t.strip()]
        text = text[: tags_match.start()].rstrip() + text[tags_match.end() :]

    # Extract and remove SOURCE: line
    source_attr = ""
    source_match = _SOURCE_LINE.search(text)
    if source_match:
        source_attr = source_match.group(1).strip()
        text = text[: source_match.start()].rstrip() + text[source_match.end() :]

    text = text.strip()

    # Extract title: prefer first # heading; fall back to first non-empty line
    title = "Untitled"
    title_match = _TITLE_LINE.search(text)
    if title_match:
        title = title_match.group(1).strip()
        # Remove the title heading line from body to avoid duplication
        text = text[: title_match.start()].rstrip() + "\n" + text[title_match.end() :]
        text = text.strip()
    else:
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if lines:
            first_line = lines[0].strip("# *_").strip()
            if 5 < len(first_line) < 250:
                title = first_line
                text = "\n".join(text.splitlines()[1:]).strip()

    return title, text, tags_raw, source_attr, news_category


def _generate_slug(title: str, pub_date, db_alias: str = "default") -> str:
    """
    Generates a unique slug: {YYYY-MM-DD}-{title-slug}.
    Appends a counter suffix if slug already exists.
    """
    date_prefix = str(pub_date)  # "2026-04-10"
    base_slug = f"{date_prefix}-{slugify(title)}"[:540]

    # Ensure uniqueness
    slug = base_slug
    counter = 1
    while DailyCaArticle.objects.using(db_alias).filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"[:550]
        counter += 1

    return slug


def _score_quality(body_md: str) -> float:
    """
    Scores article quality 0.0–10.0 based on observable signals.

    Signals:
      +3.0  word count in 450–800 range (target band)
      +2.0  has callout box (:::callout)
      +2.0  has ## section headings (structured article)
      +1.5  has [[concept links]] (analytical depth)
      +1.5  no forbidden exam phrases (editorial quality)
      ────
       10.0 max
    """
    if not body_md:
        return 0.0

    score = 0.0
    lower = body_md.lower()
    word_count = len(body_md.split())

    if _QUALITY_MIN_WORDS <= word_count <= _QUALITY_MAX_WORDS:
        score += 3.0
    elif word_count > 300:
        score += 1.5  # partial credit for reasonable length

    if ":::callout" in body_md:
        score += 2.0

    if re.search(r"^##\s+\w", body_md, re.MULTILINE):
        score += 2.0

    if "[[" in body_md and "]]" in body_md:
        score += 1.5

    has_forbidden = any(phrase in lower for phrase in _FORBIDDEN_PHRASES)
    if not has_forbidden:
        score += 1.5

    return round(min(score, 10.0), 2)


# ── Main Service ──────────────────────────────────────────────────────────────


class DailyCaGeneratorService:
    """
    Orchestrates the full Daily CA article generation pipeline.

    Usage (from generate_daily_ca management command):
        results = DailyCaGeneratorService.run_generation_cycle(
            proposals=approved_proposals,
            groq_calls_used=0,
        )
    """

    MAX_WORDS = 800
    MAX_GROQ_CALLS = 25  # session safety cap across all cycles

    @classmethod
    def run_generation_cycle(
        cls,
        proposals: list,
        groq_calls_used: int = 0,
        db_alias: str = "default",
    ) -> dict:
        """
        Main entry point. Processes each approved proposal as one complete atomic cycle.
        Stops gracefully when session cap is reached.
        Failed cycles do not stop the run — marked 'failed' and skipped.

        AFTER all cycles: triggers background static generation for topics without static.

        Returns summary dict:
          {generated, failed, capped, static_triggered, total, groq_calls_used}
        """
        results = {
            "generated": 0,
            "failed": 0,
            "capped": 0,
            "static_triggered": 0,
            "total": len(proposals),
            "groq_calls_used": groq_calls_used,
        }
        pending_static_topic_ids: list[UUID] = []

        for i, proposal in enumerate(proposals, 1):
            logger.info(
                "cycle_starting",
                cycle=i,
                total=len(proposals),
                title=proposal.title[:80],
                groq_calls_so_far=groq_calls_used,
            )

            # ── Pre-check session cap ─────────────────────────────────────────
            if groq_calls_used >= cls.MAX_GROQ_CALLS:
                logger.warning(
                    "session_cap_reached",
                    cap=cls.MAX_GROQ_CALLS,
                    at_cycle=i,
                    remaining=len(proposals) - i + 1,
                )
                for p in proposals[i - 1 :]:
                    p.status = "queued_next_run"
                    p.save(using=db_alias, update_fields=["status"])
                results["capped"] = len(proposals) - i + 1
                break

            # ── Run one cycle ─────────────────────────────────────────────────
            try:
                article, calls_this_cycle, needs_static = cls._run_single_cycle(
                    proposal, db_alias=db_alias
                )
                groq_calls_used += calls_this_cycle
                results["generated"] += 1

                if needs_static and proposal.topic_id:
                    pending_static_topic_ids.append(proposal.topic_id)

                logger.info(
                    "cycle_complete",
                    cycle=i,
                    total=len(proposals),
                    article_id=str(article.id),
                    title=article.title[:80],
                    quality_score=article.quality_score,
                    word_count=len(article.body_md.split()),
                    had_static=not needs_static,
                    groq_calls_total=groq_calls_used,
                )

            except Exception as exc:
                sentry_sdk.capture_exception(exc)
                logger.error(
                    "cycle_failed",
                    cycle=i,
                    proposal_id=str(proposal.id),
                    title=proposal.title[:80],
                    error=str(exc),
                    exc_info=True,
                )
                try:
                    proposal.status = "failed"
                    proposal.save(using=db_alias, update_fields=["status"])
                except Exception:
                    pass
                results["failed"] += 1
                # DO NOT break — a failed cycle is not catastrophic — continue

        results["groq_calls_used"] = groq_calls_used

        # ── Post-cycle: trigger background static generation ──────────────────
        if pending_static_topic_ids:
            logger.info(
                "post_cycle_static_trigger_start",
                topic_count=len(pending_static_topic_ids),
            )
            triggered = StaticBackgroundService.trigger_pending_static_generation(
                pending_static_topic_ids
            )
            results["static_triggered"] = triggered
            logger.info(
                "post_cycle_static_trigger_done",
                triggered=triggered,
                total_queued=len(pending_static_topic_ids),
            )

        logger.info("generation_run_complete", **results)
        return results

    @classmethod
    def _run_single_cycle(
        cls, proposal: CaDailyProposal, db_alias: str = "default"
    ) -> tuple:
        """
        One complete, atomic CA article generation cycle for a single proposal.
        Generates ONLY the CA article — does NOT block on or trigger static generation.

        Steps:
          1. Static background check (instant — get_background_facts returns immediately)
          2. Wiki enrichment (conditional — only for thin CA source, 0 GROQ calls)
          3. Build prompt + call LLM (1 GROQ call — writer mode)
          4. Parse response (title, body_md, tags_raw, source_attr)
          5. Word count enforcement (hard cap MAX_WORDS)
          6. Save DailyCaArticle
          7. Concept Page resolution [[term]] → /concepts/slug (0–8 GROQ calls)
          8. Keyword tag linking (1 GROQ call if no overrides match)
          9. Save DailyCaStaticLink if static existed (Case A only)
         10. Update proposal → status='generated'

        Returns: (DailyCaArticle, int calls_used, bool needs_static)
        """
        calls_used = 0
        needs_static = False

        with transaction.atomic(using=db_alias):
            # ── STEP 1: Static background (instant, never blocks) ─────────────
            static_facts = StaticBackgroundService.get_background_facts(
                proposal.topic_id
            )
            book_content_id = (
                static_facts.get("book_content_id") if static_facts else None
            )
            if static_facts is None:
                needs_static = True

            # ── STEP 2: Enriched CA context + Wiki enrichment (0 GROQ calls) ────
            # Phase D1: fetch chunks + parent article content for richer input.
            # chunk_word_count is the word count of chunks ONLY — used for wiki
            # enrichment threshold independent of how much parent content was found.
            ca_text, chunk_word_count = _fetch_enriched_ca_context(
                proposal.ca_chunk_ids, db_alias=db_alias
            )
            wiki_data: dict = {}
            topic_name_for_wiki = (
                proposal.topic.name if proposal.topic else proposal.title
            )
            # Wiki enrichment: trigger when chunk text is thin (< 300 words).
            # Uses chunk_word_count, not total enriched text length, so adding
            # parent content doesn't suppress wiki enrichment for genuinely thin sources.
            if chunk_word_count < 300:
                wiki_data = WikiEnrichmentService.get_enrichment(topic_name_for_wiki)

            # ── STEP 3: Build prompt + LLM call (1 GROQ call — writer mode) ───
            prompt = build_ca_prompt(
                ca_chunks_text=ca_text,
                static_key_facts=static_facts,
                wiki_enrichment=wiki_data if wiki_data else None,
                subject_name=proposal.subject_name or "",
                topic_name=proposal.topic.name if proposal.topic else proposal.title,
            )

            raw_response = llm_call(prompt, mode="standard")
            calls_used += 1
            time.sleep(INTER_CALL_SLEEP)

            # ── STEP 4: Parse LLM response ─────────────────────────────────────
            title, body_md, tags_raw, source_attr, news_category = _parse_response(
                raw_response
            )

            # Fallback: use proposal title if LLM didn't produce one
            if not title or title == "Untitled":
                title = proposal.title

            # ── STEP 5: Word count enforcement ────────────────────────────────
            word_count = len(body_md.split())
            if word_count > cls.MAX_WORDS:
                # Truncate at word boundary — preserve complete sentences where possible
                words = body_md.split()
                body_md = " ".join(words[: cls.MAX_WORDS])
                word_count = cls.MAX_WORDS

            # ── STEP 6: Save DailyCaArticle ───────────────────────────────────
            slug = _generate_slug(title, proposal.date, db_alias=db_alias)

            article = DailyCaArticle.objects.using(db_alias).create(
                title=title,
                slug=slug,
                topic=proposal.topic,
                subject_name=proposal.subject_name or "",
                gs_paper=proposal.gs_paper or "",
                news_category=news_category,
                published_date=proposal.date,
                body_md=body_md,
                body_md_processed="",  # filled in STEP 7
                news_context=proposal.description or "",
                sources_used=proposal.source_urls or [],
                static_background_id=book_content_id,
                hero_image_url="",  # Cloudinary phase — later
                ca_chunk_ids=proposal.ca_chunk_ids or [],
                quality_score=_score_quality(body_md),
                is_published=False,
                generation_metadata={
                    "groq_model": "llama-3.3-70b-versatile",
                    "word_count": word_count,
                    "subject": proposal.subject_name or "",
                    "had_static_anchor": static_facts is not None,
                    "had_wiki_enrichment": bool(wiki_data),
                    "had_enriched_ca_context": bool(ca_text),
                    "ca_context_chars": len(ca_text),
                    "chunk_word_count": chunk_word_count,
                    "source_attr": source_attr,
                },
            )

            # ── STEP 7: Concept Page resolution ───────────────────────────────
            # [[term]] → [term](/concepts/slug) in body_md_processed
            body_md_processed = ConceptPageResolver.process_and_replace(
                body_md, article.id, db_alias=db_alias
            )
            calls_used += ConceptPageResolver.last_new_concept_calls
            article.body_md_processed = body_md_processed
            article.save(using=db_alias, update_fields=["body_md_processed"])

            # ── STEP 8: Keyword tag linking ────────────────────────────────────
            # Only use LLM-generated tags_raw as overrides when it has ≥ 5 tags.
            # Fewer than 5 means the LLM under-delivered — fall through to a fresh
            # GROQ extraction call from TagService to guarantee the 5–8 minimum.
            _use_tag_overrides = len(tags_raw) >= 5
            TagService.extract_and_link_tags(
                article_text=body_md,
                content_type="daily_ca",
                object_id=article.id,
                overrides=tags_raw if _use_tag_overrides else None,
                db_alias=db_alias,
            )
            # Count 1 GROQ call if overrides were insufficient (service called LLM itself)
            if not _use_tag_overrides:
                calls_used += 1
                time.sleep(INTER_CALL_SLEEP)

            # ── STEP 9: DailyCaStaticLink (Case A only — static existed) ──────
            if book_content_id:
                DailyCaStaticLink.objects.using(db_alias).get_or_create(
                    daily_article=article,
                    book_content_id=book_content_id,
                    defaults={"link_reason": "same_topic"},
                )

            # ── STEP 10: Update proposal ───────────────────────────────────────
            proposal.status = "generated"
            proposal.generated_article = article  # FK — assign model instance directly
            proposal.save(
                using=db_alias, update_fields=["status", "generated_article_id"]
            )

            logger.info(
                "single_cycle_done",
                article_id=str(article.id),
                title=article.title[:80],
                calls_used=calls_used,
                needs_static=needs_static,
                quality_score=article.quality_score,
            )

            return article, calls_used, needs_static
