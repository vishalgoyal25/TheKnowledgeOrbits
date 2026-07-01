"""
engines/daily_ca/services/generator_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase J3 — DailyCaGeneratorService
Phase D1 (FEATURES3) — Enriched CA context: combines chunk text + parent article content.

Main entry point: run_generation_cycle(proposals, groq_calls_used=0) → dict

Architecture: CA-First, Static-Background
  _run_single_cycle()       — generates ONE CA article (fast, ~15-20s)
                              never blocks, never waits for static
  run_generation_cycle()    — runs all cycles sequentially; static content
                              generation is handled by a separate cron job (Phase B)

GROQ call budget per cycle:
  1 call  — main CA article generation (writer mode, high token limit)
  0-8     — new concept page stubs (1 per unknown [[term]], max 8)
  1 call  — keyword tag extraction (standard mode, only if overrides insufficient)
  ────
  ~2-10 calls per cycle typical. Session cap = 100 across all cycles.

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

import sentry_sdk
import structlog
from django.db import transaction
from django.utils.text import slugify

from engines.book_content.services.llm_service import INTER_CALL_SLEEP, llm_call
from engines.book_content.services.retrieval_service import (
    as_static_facts,
    retrieve_grounding,
)
from engines.daily_ca.models import CaDailyProposal, DailyCaArticle, DailyCaStaticLink
from engines.daily_ca.services.prompt_builder import (
    build_ca_prompt,
)
from engines.daily_ca.services.static_background_service import StaticBackgroundService
from engines.daily_ca.services.wiki_enrichment_service import WikiEnrichmentService
from engines.tags.services.concept_resolver import ConceptPageResolver
from engines.tags.services.tag_service import TagService

logger = structlog.get_logger(__name__)

# ── Rate-limit guard — sleep between articles ────────────────────────────────
# GROQ free tier: 6,000 tokens/minute per key.  Each article consumes ~20,000
# tokens (2 calls × ~10,000 tokens each).  With 2 keys that's 12,000 TPM, so
# one article needs ~100 s of bucket-refill time.  We sleep 90 s between cycles
# (generation itself takes ~30 s, meaning the bucket has already partially
# refilled by the time we enter the sleep).  This prevents the chain of 429s
# that would otherwise waste 4 minutes of retry back-off per article.
INTER_CYCLE_SLEEP = 90  # seconds — proactive throttle between Daily CA articles

# ── Quality scoring constants ─────────────────────────────────────────────────
_QUALITY_MIN_WORDS = 450
_QUALITY_MAX_WORDS = 1000

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
          enriched_text     — combined text capped at 6000 chars, structured with
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
                        # First 1500 chars captures headline + lead paragraphs
                        # where named details (officials, figures, dates) concentrate
                        parent_content_parts.append(
                            f"[Source: {source_name}]\n{content[:1500]}"
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

        # Cap at 6000 chars — richer context window (up from 4000)
        return combined[:6000], chunk_word_count

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


# ── Phase H — Title quality guard ────────────────────────────────────────────

_FORBIDDEN_TITLE_OPENERS: tuple[str, ...] = (
    "introduction to",
    "overview of",
    "understanding",
    "a look at",
    "examining",
    "an analysis of",
    "the role of",
    "importance of",
    "all you need to know",
    "everything about",
    "what is",
    "what are",
    "a brief",
    "a study of",
    "exploring",
)


def _validate_title(title: str, fallback_title: str) -> str:
    """
    Phase H — Post-processing title quality guard.

    If the LLM produces a textbook-style title (starting with a forbidden opener),
    fall back to the proposal title which is always sourced from real news headlines.

    The proposal title is generated by a separate GROQ call in generate_ca_proposals
    with strict news-headline instructions, so it is a reliable fallback.
    """
    lower = title.lower().strip()
    for opener in _FORBIDDEN_TITLE_OPENERS:
        if lower.startswith(opener):
            logger.info(
                "generator_title_rejected",
                rejected_title=title[:80],
                opener_matched=opener,
                fallback_title=fallback_title[:80],
            )
            return fallback_title
    return title


def _simplify_text(text: str) -> str:
    """
    Phase G — Post-processing language simplification.

    Replaces genuinely obscure vocabulary that LLMs default to but that falls
    outside standard Indian newspaper/news-channel language (The Hindu, Indian
    Express, Times of India, NDTV, DD News register).

    Standard applied: a smart Indian 12th-class student or working professional
    should understand every word without consulting a dictionary.

    WHAT THIS DOES NOT TOUCH:
      - Common Indian legal/policy English naturally used in Indian journalism:
        prima facie, inter alia, vis-à-vis, notwithstanding, aforementioned,
        hitherto, heretofore, wherein — these are standard in Indian discourse
      - Domain-specific technical terms (quantum, genome, fiscal deficit) — these
        are explained by context and are the article's educational content
      - Words that appear in Indian newspaper editorials regularly

    WHAT THIS REPLACES:
      Obscure Latinate/literary vocabulary that LLMs over-use but Indian readers
      would rarely encounter — words that exist in advanced western academic
      writing but not in standard Indian press.

    Uses whole-word regex to avoid partial replacements (e.g., "ameliorated"
    inside a longer sentence). Case-preserving where possible.
    """
    import re

    # (pattern, replacement) — order matters: longer phrases before single words
    _REPLACEMENTS: list[tuple[str, str]] = [
        # Obscure Latinate verbs
        (r"\bameliorate[sd]?\b", "improve"),
        (r"\bamelioration\b", "improvement"),
        (r"\beschew[sed]*\b", "avoid"),
        (r"\bobfuscat(?:e[sd]?|ing|ion)\b", "complicate"),
        (r"\belucidat(?:e[sd]?|ing|ion)\b", "explain"),
        (r"\bvitiat(?:e[sd]?|ing|ion)\b", "undermine"),
        (r"\bmilitate[sd]? against\b", "work against"),
        (r"\bbelabou?r(?:ed|ing)?\b", "overstate"),
        (r"\bpropitiat(?:e[sd]?|ing|ion)\b", "appease"),
        # Obscure adjectives
        (r"\bpropitious\b", "favourable"),
        (r"\binimical\b", "harmful"),
        (r"\bsalubrious\b", "beneficial"),
        (r"\bperspicuous\b", "clear"),
        (r"\brecondite\b", "obscure"),
        (r"\bperspicacious\b", "perceptive"),
        (r"\btendentious\b", "one-sided"),
        (r"\bpusillanimous\b", "cowardly"),
        (r"\binchoate\b", "undeveloped"),
        (r"\bquotidian\b", "everyday"),
        (r"\bliminal\b", "transitional"),
        (r"\bsolipsistic\b", "self-centred"),
        (r"\bnescient\b", "ignorant"),
        # Obscure academic/philosophical adjectives rare in Indian press
        (r"\bepistemological(?:ly)?\b", "knowledge-based"),
        (r"\bontological(?:ly)?\b", "fundamental"),
        (r"\bteleological(?:ly)?\b", "goal-driven"),
        # Obscure nouns
        (r"\bapotheosis\b", "pinnacle"),
        (r"\bnescience\b", "ignorance"),
        (r"\bblandishments\b", "persuasion"),
        (r"\bsolecism\b", "error"),
        (r"\bchicanery\b", "trickery"),
        (r"\bopprobrium\b", "criticism"),
        (r"\bturpitude\b", "misconduct"),
        (r"\bmalfeasance\b", "wrongdoing"),
        (r"\bshibboleth\b", "outdated belief"),
        (r"\bpalimpsest\b", "layered history"),
    ]

    for pattern, replacement in _REPLACEMENTS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text


def _truncate_body(body_md: str, max_words: int) -> str:
    """
    Truncates markdown at a clean paragraph boundary without destroying structure.

    Unlike the naive split()+join() approach, this:
      - Preserves all newlines, headings (##), bullet points, tables
      - NEVER cuts inside a :::callout ... ::: block
      - Stops at the first blank line AFTER max_words is reached
      - Keeps [[concept]] link patterns intact for ConceptPageResolver

    Strategy:
      Walk line-by-line, accumulating word count.
      Once we exceed max_words, wait for the next blank line → clean stop.
      Callout blocks are always included whole even if slightly over limit.
    """
    lines = body_md.split("\n")
    result: list[str] = []
    word_count = 0
    in_callout = False

    for line in lines:
        # Detect callout start
        if line.strip().startswith(":::callout"):
            in_callout = True

        if in_callout:
            # Always include lines inside a callout — never cut mid-block
            result.append(line)
            word_count += len(line.split())
            if line.strip() == ":::":
                in_callout = False
            continue

        # Over limit: stop at the next blank line (clean paragraph boundary)
        if word_count >= max_words:
            if not line.strip():
                break
            # Non-blank line after limit: include it so we don't cut mid-sentence
            result.append(line)
            word_count += len(line.split())
            continue

        result.append(line)
        word_count += len(line.split())

    final = "\n".join(result).rstrip()

    # Hard-limit fallback: single-line content (no paragraph breaks) can slip
    # through the blank-line stop above and still exceed max_words.
    final_words = final.split()
    if len(final_words) > max_words:
        truncated = " ".join(final_words[:max_words])
        # Try to end at the last sentence boundary within the truncated text
        for sep in (". ", "! ", "? "):
            last = truncated.rfind(sep)
            if last > max_words * 3:  # at least 75% of content preserved
                return truncated[: last + 1].rstrip()
        return truncated

    return final


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

    MAX_WORDS = 1000
    MAX_GROQ_CALLS = 100  # session safety cap across all cycles

    @classmethod
    def run_generation_cycle(
        cls,
        proposals: list,
        groq_calls_used: int = 0,
        db_alias: str = "default",
        auto_publish: bool = False,
    ) -> dict:
        """
        Main entry point. Processes each approved proposal as one complete atomic cycle.
        Stops gracefully when session cap is reached.
        Failed cycles do not stop the run — marked 'failed' and skipped.

        Static content generation is handled by the separate `generate_static_content`
        management command (Phase B) — it runs as a dedicated Render cron job AFTER
        the full CA+Quiz pipeline completes.

        Returns summary dict:
          {generated, failed, capped, static_triggered, total, groq_calls_used}
        """
        results = {
            "generated": 0,
            "failed": 0,
            "capped": 0,
            "static_triggered": 0,  # always 0 — static is handled by separate cron job
            "total": len(proposals),
            "groq_calls_used": groq_calls_used,
        }

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

                # ── STEP 10b: Hero image (outside atomic tx — HTTP I/O) ───────
                # Called here so it never holds the DB transaction open.
                # Failure is silently swallowed — image is optional, article is not.
                try:
                    from engines.daily_ca.services.image_service import HeroImageService

                    hero_url = HeroImageService.fetch_and_upload(
                        source_urls=proposal.source_urls or [],
                        topic_name=(
                            proposal.topic.name if proposal.topic else proposal.title
                        ),
                        article_id=str(article.id),
                    )
                    if hero_url:
                        article.hero_image_url = hero_url
                        article.save(using=db_alias, update_fields=["hero_image_url"])
                except Exception as _img_exc:
                    sentry_sdk.capture_exception(_img_exc)
                    logger.warning(
                        "hero_image_step_failed",
                        article_id=str(article.id),
                        error=str(_img_exc)[:150],
                    )

                # ── Publish immediately if auto_publish ───────────────────────
                if auto_publish:
                    article.is_published = True
                    article.save(using=db_alias, update_fields=["is_published"])
                    logger.info(
                        "article_auto_published",
                        article_id=str(article.id),
                        title=article.title[:60],
                    )

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

            # ── Inter-cycle rate-limit guard ──────────────────────────────────
            # Sleep between articles (not after the last one) so the GROQ token
            # bucket has time to refill before the next 20,000-token cycle.
            # Without this every article after #2 hits 429 on the first attempt
            # and wastes 4+ minutes of exponential back-off.
            if i < len(proposals):
                logger.info(
                    "inter_cycle_sleep",
                    sleeping_seconds=INTER_CYCLE_SLEEP,
                    next_cycle=i + 1,
                    total=len(proposals),
                )
                time.sleep(INTER_CYCLE_SLEEP)

        results["groq_calls_used"] = groq_calls_used

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

            # ── STEP 2: Enriched CA context (the NEWS — proposal's own chunks) ──
            # Phase D1: fetch chunks + parent article content for richer input.
            # chunk_word_count is the word count of chunks ONLY — used for the wiki
            # fallback threshold independent of how much parent content was found.
            ca_text, chunk_word_count = _fetch_enriched_ca_context(
                proposal.ca_chunk_ids, db_alias=db_alias
            )
            topic_name_for_wiki = (
                proposal.topic.name if proposal.topic else proposal.title
            )

            # ── STEP 2b: RAG grounding — PRIMARY theory source (Phase 3) ───────
            # Publish-agnostic semantic + cross-subject retrieval from the book
            # corpus, feeding the existing CONCEPTUAL DEPTH ANCHOR (static_key_facts)
            # slot. Supersedes StaticBackgroundService's exact-topic regex anchor,
            # which is effectively dead (only 2/162 BookContent published — it gates
            # on is_published, the gateway does not). k_ca=0: daily_ca's news is the
            # proposal's own CA chunks; the gateway supplies THEORY only.
            grounding = retrieve_grounding(
                seed_topic_id=proposal.topic_id,
                query=topic_name_for_wiki,
                k_ca=0,
                db_alias=db_alias,
            )
            grounding_facts = (
                as_static_facts(grounding, title=topic_name_for_wiki)
                if grounding.get("book_chunks")
                else None
            )

            # Theory-anchor priority: RAG grounding → published static → none.
            static_key_facts = grounding_facts or static_facts

            # ── STEP 2c: Wiki enrichment — FALLBACK ONLY (0 GROQ calls) ────────
            # Fires only when RAG produced NO theory AND the CA source is thin.
            # Keeps wiki as a true last resort, not a default.
            wiki_data: dict = {}
            if not grounding_facts and chunk_word_count < 300:
                wiki_data = WikiEnrichmentService.get_enrichment(topic_name_for_wiki)

            # ── STEP 3: Build prompt + LLM call (1 GROQ call — writer mode) ───
            prompt = build_ca_prompt(
                ca_chunks_text=ca_text,
                static_key_facts=static_key_facts,
                wiki_enrichment=wiki_data if wiki_data else None,
                subject_name=proposal.subject_name or "",
                topic_name=proposal.topic.name if proposal.topic else proposal.title,
            )

            raw_response = llm_call(prompt, mode="writer")
            calls_used += 1
            time.sleep(INTER_CALL_SLEEP)

            if not raw_response:
                raise RuntimeError(
                    f"LLM permanently failed for '{proposal.title[:60]}' — "
                    "empty response after all retries. Cycle aborted, no article saved."
                )

            # ── STEP 4: Parse LLM response ─────────────────────────────────────
            title, body_md, tags_raw, source_attr, news_category = _parse_response(
                raw_response
            )

            # Fallback: use proposal title if LLM didn't produce one
            if not title or title == "Untitled":
                title = proposal.title

            # ── STEP 4b: Title quality guard ──────────────────────────────────
            title = _validate_title(title, fallback_title=proposal.title)

            # ── STEP 4c: Language simplification (post-processing, no LLM call) ─
            body_md = _simplify_text(body_md)

            # ── STEP 5: Word count enforcement ────────────────────────────────
            word_count = len(body_md.split())
            if word_count > cls.MAX_WORDS:
                # Truncate at paragraph boundary — preserves headings, bullets, callouts
                body_md = _truncate_body(body_md, cls.MAX_WORDS)
                word_count = len(body_md.split())

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
                    "groq_model": "openai/gpt-oss-120b",
                    "word_count": word_count,
                    "subject": proposal.subject_name or "",
                    # Phase 3 — RAG grounding is now the PRIMARY theory anchor.
                    "had_rag_grounding": bool(grounding_facts),
                    "grounding_stats": grounding.get("stats", {}),
                    "grounding_provenance": grounding.get("provenance", []),
                    "had_static_anchor": static_facts
                    is not None,  # legacy published-static path (secondary)
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
