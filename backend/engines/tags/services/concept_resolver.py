"""
engines/tags/services/concept_resolver.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase E2 — ConceptPageResolver: Inline [[term]] → /concepts/slug link resolution.
Phase B2 (FEATURES3) — Enhanced deduplication: dual-field matching + normalization.

Responsibilities:
  1. process_and_replace() — scans article markdown for [[term]] patterns,
     resolves each to a ConceptPage (reuse existing or create new stub),
     replaces [[term]] → [term](/concepts/slug),
     writes ConceptArticleLink junction rows,
     enforces max 8 concept links per article.

  2. _resolve_or_create() — three-pass resolution:
       exact slug → exact name → fuzzy slug + normalized slug → create stub

Design rules enforced here:
  - NEVER creates duplicate/near-duplicate ConceptPages (difflib threshold 0.75):
      Pass 1: exact slug  →  Pass 2: exact name  →  Pass 3: fuzzy + normalized fuzzy
  - Normalization strips filler words so "election-commission" matches
    "election-commission-of-india", and "clnda" can match on name exactly
  - Max 8 concept links per article (over-limit terms rendered as plain text)
  - New concept stub creation: 1 GROQ call → brief_description only
    (body_md left empty; is_content_ready=False until full generation phase)
  - INTER_CALL_SLEEP respected after every new concept creation (GROQ rate limit)
  - usage_count incremented atomically via F() on ConceptPage
  - All exceptions captured to Sentry + structlog; never propagated to caller

Three-entity rule (from models.py — never confuse):
  Tag          → article label    → /tags/[slug]     → aggregation page
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
SIMILARITY_THRESHOLD = 0.85  # Phase D: raised from 0.75 — prevents false positives like
# national-solar-mission→national-labour-commission,
# trinamool-congress→indian-national-trade-union-congress
MAX_CONCEPT_LINKS = 8  # per article hard limit

# Regex: matches [[any text here]] — captures the inner term
_CONCEPT_PATTERN = re.compile(r"\[\[([^\]\[]+)\]\]")

# ── Normalisation helpers ─────────────────────────────────────────────────────
# Words that do NOT carry semantic meaning for slug-matching purposes.
# Stripped before fuzzy comparison to collapse near-duplicate concept pages
# across all four GS subject areas:
#
#   GS1 (History/Geography/Culture/Society):
#     "sendai-framework-for-disaster-risk-reduction" → "sendai-disaster-risk-reduction"
#     "ancient-monuments-act" → "ancient-monuments"
#     "convention-on-biological-diversity" → "biological-diversity"
#
#   GS2 (Polity/Governance/IR):
#     "election-commission-of-india" → "election"
#     "civil-liability-for-nuclear-damage-act" → "civil-liability-nuclear-damage"
#     "right-to-information-act" → "right-information"
#     "foreign-contribution-regulation-act" → "foreign-contribution-regulation"
#
#   GS3 (Economy/S&T/Environment/Security/Disaster):
#     "national-disaster-management-authority" → "disaster"
#     "department-of-space" → "space"
#     "pradhan-mantri-jan-dhan-yojana" → "pradhan-mantri-jan-dhan"
#     "national-green-tribunal" → "green"
#
#   GS4 (Ethics/Integrity/Aptitude):
#     "central-vigilance-commission" → "vigilance"
#     "lokpal-and-lokayuktas-act" → "lokpal-lokayuktas"
_FILLER_WORDS = frozenset(
    {
        # ── Articles, prepositions, connectors ───────────────────────────────────
        "a",
        "an",
        "the",
        "of",
        "for",
        "in",
        "at",
        "by",
        "to",
        "on",
        "with",
        "from",
        "into",
        "about",
        "under",
        "over",
        "between",
        "among",
        "via",
        "and",
        "or",
        # ── Geographic / nationality qualifiers (GS1, GS2, GS3) ─────────────────
        "india",
        "indian",
        "bharat",
        "national",
        "central",
        "state",
        "union",
        "global",
        "world",
        "international",
        # ── Organisational suffixes — GS2 (Polity/Governance/IR) ─────────────────
        "authority",
        "board",
        "committee",
        "commission",
        "council",
        "tribunal",
        "bureau",
        "agency",
        "body",
        "wing",
        "cell",
        "ministry",
        "department",
        "office",
        "secretariat",
        "parliament",
        "assembly",
        "house",
        "court",
        "bench",
        # ── Document/instrument type suffixes (GS2, GS3) ─────────────────────────
        "act",
        "bill",
        "amendment",
        "ordinance",
        "notification",
        "treaty",
        "agreement",
        "accord",
        "protocol",
        "convention",
        "framework",
        "resolution",
        "declaration",
        "directive",
        # ── Programme/initiative suffixes — GS3 (Economy/Schemes/Environment) ────
        "policy",
        "scheme",
        "programme",
        "program",
        "mission",
        "yojana",
        "abhiyan",
        "project",
        "plan",
        "initiative",
        "drive",
        "campaign",
        "fund",
        "trust",
        "foundation",
        # ── Generic descriptor modifiers (all subjects) ───────────────────────────
        "new",
        "old",
        "revised",
        "amended",
        "special",
        "general",
        "key",
        "major",
        "main",
        "core",
        "primary",
        "public",
        "private",
        "civil",
        "development",
        "affairs",
        "relations",
        "regulation",
        "reform",
        "review",
        "management",
        "administration",
        "governance",
    }
)


def _slug_has_digits(slug: str) -> bool:
    """
    Returns True if the slug contains any digit character.

    Numeric slugs like "government-of-india-act-1935", "article-21", "schedule-7"
    must NEVER be fuzzy-matched — a high similarity score between two act numbers
    is meaningless and produces wrong concept links
    (government-of-india-act-1935 → indian-government, etc.).
    Exact slug / exact name match (Pass 1 / Pass 2) is the only safe path.
    """
    return any(ch.isdigit() for ch in slug)


def _normalize_for_match(text: str) -> str:
    """
    Strips filler words and normalises to lowercase hyphenated form.
    Used for fuzzy matching only — NOT for slug generation.
    Falls back to the original text if all words are stripped (prevents empty keys).

    Examples (covering all GS subject domains):
      GS1: "ancient-monuments-act"                → "ancient-monuments"
      GS1: "convention-on-biological-diversity"   → "biological-diversity"
      GS2: "election-commission-of-india"         → "election"
      GS2: "right-to-information-act"             → "right-information"
      GS2: "civil-liability-for-nuclear-damage-act" → "civil-liability-nuclear-damage"
      GS3: "pm-kisan-scheme"                      → "pm-kisan"
      GS3: "national-green-tribunal"              → "green"
      GS4: "central-vigilance-commission"         → "vigilance"
    """
    words = re.split(r"[-\s]+", text.lower().strip())
    filtered = [w for w in words if w and w not in _FILLER_WORDS]
    return "-".join(filtered) if filtered else text.lower()


# ── Prompts ───────────────────────────────────────────────────────────────────
_BRIEF_DESCRIPTION_PROMPT = """You are an encyclopaedic reference writer.
Write 2–3 concise sentences explaining "{term}" for a curious, educated reader.
Cover: what it is, its significance, and one concrete fact or example.
Do NOT use bullet points. Plain prose only. Max 60 words.
Do NOT mention UPSC, exam, aspirants, or GS paper.
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
    def process_and_replace(
        cls,
        body_md: str,
        article_id: UUID | None = None,
        book_content_id: UUID | None = None,
        db_alias: str = "default",
    ) -> str:
        """
        Scan body_md for [[term]] patterns, resolve each to a ConceptPage,
        replace with [term](/concepts/slug), and write ConceptArticleLink rows.

        Exactly ONE of article_id or book_content_id must be provided.
          article_id       — UUID of the owning DailyCaArticle
          book_content_id  — UUID of the owning BookContent (K2)

        Over-limit terms (> MAX_CONCEPT_LINKS) are rendered as plain text
        with no link — never silently dropped or errored.

        Returns:
            Processed markdown with [[term]] replaced by links or plain text.
        """
        cls.last_new_concept_calls = 0
        links_added = 0
        owner_ref = str(article_id or book_content_id)

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
                    owner=owner_ref,
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
                    owner=owner_ref,
                    error=str(exc)[:200],
                )
                return term  # graceful degradation — plain text

            # Write junction row (idempotent) — branch on article type
            try:
                if article_id:
                    _, created = ConceptArticleLink.objects.using(
                        db_alias
                    ).get_or_create(
                        concept_page=concept,
                        daily_ca_article_id=article_id,
                        defaults={"book_content_article": None},
                    )
                else:
                    _, created = ConceptArticleLink.objects.using(
                        db_alias
                    ).get_or_create(
                        concept_page=concept,
                        book_content_article_id=book_content_id,
                        defaults={"daily_ca_article": None},
                    )
                if created:
                    ConceptPage.objects.using(db_alias).filter(pk=concept.pk).update(
                        usage_count=F("usage_count") + 1
                    )
                    logger.info(
                        "concept_resolver_link_created",
                        concept=concept.name,
                        slug=concept.slug,
                        owner=owner_ref,
                    )
            except Exception as exc:
                sentry_sdk.capture_exception(exc)
                logger.error(
                    "concept_resolver_link_write_failed",
                    term=term,
                    concept_slug=concept.slug,
                    owner=owner_ref,
                    error=str(exc)[:200],
                )
                return term  # link write failed — degrade to plain text

            links_added += 1
            return f"[{term}](/concepts/{concept.slug})"

        processed = _CONCEPT_PATTERN.sub(replace_match, body_md)

        logger.info(
            "concept_resolver_complete",
            owner=owner_ref,
            links_added=links_added,
            new_concept_stubs_created=cls.last_new_concept_calls,
        )
        return processed

    # ── Private Helpers ────────────────────────────────────────────────────────

    @classmethod
    def _resolve_or_create(cls, term: str, db_alias: str = "default") -> ConceptPage:
        """
        Phase B2 — Three-pass concept resolution with normalized fuzzy matching.

        Resolution order:
          Pass 1: Exact slug match
          Pass 2: Exact name match (case-insensitive) — catches "CLNDA" vs stored name
          Pass 3a: Fuzzy match on raw slug (threshold 0.75)
          Pass 3b: Fuzzy match on normalized slug — strips filler words so
                   "election-commission" matches "election-commission-of-india"
        Creates a new stub only when all passes fail.

        Args:
            term:     Raw term string extracted from [[term]] bracket.
            db_alias: Django database alias (default: "default").

        Returns:
            ConceptPage instance (existing or newly created stub).

        Raises:
            Exception if both DB lookup and creation fail.
        """
        slug = slugify(term)

        # Pass 1: exact slug
        existing = ConceptPage.objects.using(db_alias).filter(slug=slug).first()
        if existing:
            logger.info(
                "concept_resolver_exact_match",
                term=term,
                slug=slug,
            )
            return existing

        # Pass 2: exact name match (case-insensitive)
        # Handles acronyms and alternate casings stored in the name field
        existing = ConceptPage.objects.using(db_alias).filter(name__iexact=term).first()
        if existing:
            logger.info(
                "concept_resolver_name_match",
                term=term,
                matched_name=existing.name,
                matched_slug=existing.slug,
            )
            return existing

        # Pass 3: load all concept slugs once, then try fuzzy variants
        all_concepts = list(ConceptPage.objects.using(db_alias).values("slug", "name"))
        if all_concepts:
            all_slugs = [c["slug"] for c in all_concepts]

            # Pass 3a: fuzzy on raw slug
            # Numeric slugs (government-of-india-act-1935, article-21 …) must NEVER
            # fuzzy-match — the number IS the identity; similarity scores are
            # meaningless across different act numbers / article numbers.
            if not _slug_has_digits(slug):
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

            # Pass 3b: fuzzy on normalized slug (strips filler words)
            # Also skipped for numeric slugs — same rationale as Pass 3a.
            if not _slug_has_digits(slug):
                norm_slug = _normalize_for_match(slug)
                norm_map = {_normalize_for_match(s): s for s in all_slugs}
                norm_matches = difflib.get_close_matches(
                    norm_slug, list(norm_map.keys()), n=1, cutoff=SIMILARITY_THRESHOLD
                )
                if norm_matches:
                    original_slug = norm_map[norm_matches[0]]
                    matched = ConceptPage.objects.using(db_alias).get(
                        slug=original_slug
                    )
                    logger.info(
                        "concept_resolver_normalized_fuzzy_match",
                        term=term,
                        input_slug=slug,
                        normalized_input=norm_slug,
                        matched_slug=original_slug,
                    )
                    return matched

        # All passes failed — create new stub with LLM-generated brief_description
        return cls._create_stub(term, slug, db_alias=db_alias)

    @classmethod
    def _create_stub(
        cls, term: str, slug: str, db_alias: str = "default"
    ) -> ConceptPage:
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
