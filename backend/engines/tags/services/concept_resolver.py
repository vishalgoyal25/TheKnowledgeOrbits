"""
engines/tags/services/concept_resolver.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase E2 — ConceptPageResolver: Inline [[term]] → /concepts/slug link resolution.

Responsibilities:
  1. process_and_replace() — scans article markdown for [[term]] patterns,
     resolves each to a ConceptPage (reuse existing or create new stub),
     replaces [[term]] → [term](/concepts/slug),
     writes ConceptArticleLink junction rows,
     enforces max 8 concept links per article.

  2. _resolve_or_create() — exact slug match → fuzzy difflib match → create
     new stub (1 GROQ call for brief_description).

Design rules enforced here:
  - NEVER creates duplicate/near-duplicate ConceptPages (difflib threshold 0.85)
  - Max 8 concept links per article (over-limit terms rendered as plain text)
  - New concept stub creation: 1 GROQ call → brief_description only
    (body_md left empty; is_content_ready=False until full generation phase)
  - INTER_CALL_SLEEP respected after every new concept creation (GROQ rate limit)
  - usage_count incremented atomically via F() on ConceptPage
  - All exceptions captured to Sentry + structlog; never propagated to caller

Three-entity rule (from models.py — never confuse):
  Tag          → article label   → /tags/[slug]     → aggregation page
  ConceptPage  → inline deep-link → /concepts/[slug] → concept detail page
  BookContent  → syllabus topic   → /learn/[slug]    → structured article
"""

import difflib
import re
import time
from uuid import UUID

import sentry_sdk
import structlog
from django.db.models import F
from django.utils.text import slugify

from engines.book_content.services.llm_service import INTER_CALL_SLEEP, llm_call
from engines.tags.models import ConceptArticleLink, ConceptPage

logger = structlog.get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
SIMILARITY_THRESHOLD = 0.85
MAX_CONCEPT_LINKS = 8  # per article hard limit

# Regex: matches [[any text here]] — captures the inner term
_CONCEPT_PATTERN = re.compile(r"\[\[([^\]\[]+)\]\]")

# ── Prompts ───────────────────────────────────────────────────────────────────
_BRIEF_DESCRIPTION_PROMPT = """You are a UPSC content expert writing a concept reference stub.

Write 2–3 concise sentences explaining "{term}" for a UPSC aspirant.
Cover: what it is, why it matters for UPSC, one key fact or context.
Do NOT use bullet points. Plain prose only. Max 60 words.

Return ONLY the description — no headings, no quotes, no extra text."""


# ── Resolver ──────────────────────────────────────────────────────────────────
class ConceptPageResolver:
    """
    Resolves [[double-bracket]] inline concept links in article markdown.

    Class-level state:
        last_new_concept_calls — count of new ConceptPage stubs created
                                 during the most recent process_and_replace() call.
                                 Reset at the start of each call.
                                 Useful for caller to log/monitor GROQ usage.

    Usage:
        processed_md = ConceptPageResolver.process_and_replace(
            body_md=article.body_md,
            article_id=article.id,
        )
    """

    last_new_concept_calls: int = 0  # class-level, reset per article

    # ── Public API ─────────────────────────────────────────────────────────────

    @classmethod
    def process_and_replace(cls, body_md: str, article_id: UUID, db_alias: str = "default") -> str:
        """
        Scan body_md for [[term]] patterns, resolve each to a ConceptPage,
        replace with [term](/concepts/slug), and write ConceptArticleLink rows.

        Over-limit terms (> MAX_CONCEPT_LINKS) are rendered as plain text
        with no link — never silently dropped or errored.

        Args:
            body_md:    Article markdown string containing [[term]] patterns.
            article_id: UUID of the owning DailyCaArticle.
            db_alias:   Django database alias (default: "default").

        Returns:
            Processed markdown with [[term]] replaced by links or plain text.
        """
        cls.last_new_concept_calls = 0
        links_added = 0

        def replace_match(match: re.Match) -> str:
            nonlocal links_added

            term = match.group(1).strip()
            if not term:
                return match.group(0)  # empty brackets — leave as-is

            # Over the limit — render as plain text, no link
            if links_added >= MAX_CONCEPT_LINKS:
                logger.info(
                    "concept_resolver_limit_reached",
                    term=term,
                    article_id=str(article_id),
                    limit=MAX_CONCEPT_LINKS,
                )
                return term

            try:
                concept = cls._resolve_or_create(term, db_alias=db_alias)
            except Exception as exc:
                sentry_sdk.capture_exception(exc)
                logger.error(
                    "concept_resolver_resolve_failed",
                    term=term,
                    article_id=str(article_id),
                    error=str(exc)[:200],
                )
                return term  # graceful degradation — plain text

            # Write junction row (idempotent)
            try:
                _, created = ConceptArticleLink.objects.using(db_alias).get_or_create(
                    concept_page=concept,
                    daily_ca_article_id=article_id,
                )
                if created:
                    ConceptPage.objects.using(db_alias).filter(pk=concept.pk).update(
                        usage_count=F("usage_count") + 1
                    )
                    logger.info(
                        "concept_resolver_link_created",
                        concept=concept.name,
                        slug=concept.slug,
                        article_id=str(article_id),
                    )
            except Exception as exc:
                sentry_sdk.capture_exception(exc)
                logger.error(
                    "concept_resolver_link_write_failed",
                    term=term,
                    concept_slug=concept.slug,
                    article_id=str(article_id),
                    error=str(exc)[:200],
                )
                return term  # link write failed — degrade to plain text

            links_added += 1
            return f"[{term}](/concepts/{concept.slug})"

        processed = _CONCEPT_PATTERN.sub(replace_match, body_md)

        logger.info(
            "concept_resolver_complete",
            article_id=str(article_id),
            links_added=links_added,
            new_concept_stubs_created=cls.last_new_concept_calls,
        )
        return processed

    # ── Private Helpers ────────────────────────────────────────────────────────

    @classmethod
    def _resolve_or_create(cls, term: str, db_alias: str = "default") -> ConceptPage:
        """
        Find an existing ConceptPage (exact or fuzzy) or create a new stub.

        Resolution order:
          1. Exact slug match
          2. Fuzzy difflib match (threshold 0.85) — prevents near-duplicates
          3. Create new stub: 1 GROQ call for brief_description

        Args:
            term:     Raw term string extracted from [[term]] bracket.
            db_alias: Django database alias (default: "default").

        Returns:
            ConceptPage instance (existing or newly created stub).

        Raises:
            Exception if both DB lookup and creation fail.
        """
        slug = slugify(term)

        # 1. Exact slug match
        existing = ConceptPage.objects.using(db_alias).filter(slug=slug).first()
        if existing:
            logger.info(
                "concept_resolver_exact_match",
                term=term,
                slug=slug,
            )
            return existing

        # 2. Fuzzy slug match — load all slugs and compare
        all_slugs = list(ConceptPage.objects.using(db_alias).values_list("slug", flat=True))
        matches = difflib.get_close_matches(
            slug, all_slugs, n=1, cutoff=SIMILARITY_THRESHOLD
        )
        if matches:
            matched = ConceptPage.objects.using(db_alias).get(slug=matches[0])
            logger.info(
                "concept_resolver_fuzzy_match",
                term=term,
                input_slug=slug,
                matched_slug=matches[0],
            )
            return matched

        # 3. No match — create new stub with LLM-generated brief_description
        return cls._create_stub(term, slug, db_alias=db_alias)

    @classmethod
    def _create_stub(cls, term: str, slug: str, db_alias: str = "default") -> ConceptPage:
        """
        Create a new ConceptPage stub.

        Calls GROQ once to generate a 2–3 sentence brief_description.
        body_md is left empty; is_content_ready remains False.
        A full generation phase will populate body_md later.

        Rate-limited: sleeps INTER_CALL_SLEEP seconds after the GROQ call.

        Args:
            term:     Display name of the concept.
            slug:     URL-safe slug derived from term.
            db_alias: Django database alias (default: "default").

        Returns:
            Newly created ConceptPage.
        """
        prompt = _BRIEF_DESCRIPTION_PROMPT.format(term=term)
        brief = llm_call(prompt, mode="standard").strip()

        # Sleep after GROQ call to respect rate limit
        time.sleep(INTER_CALL_SLEEP)

        # Trim to safe length
        if len(brief) > 500:
            brief = brief[:497] + "..."

        concept = ConceptPage.objects.using(db_alias).create(
            name=term,
            slug=slug,
            brief_description=brief,
            body_md="",
            is_content_ready=False,
            usage_count=0,
        )

        cls.last_new_concept_calls += 1

        logger.info(
            "concept_resolver_stub_created",
            name=term,
            slug=slug,
            brief_length=len(brief),
        )
        return concept
