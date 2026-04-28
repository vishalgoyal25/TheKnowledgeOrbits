"""
engines/tags/services/tag_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase E1 — TagService: Keyword Tag extraction and linking.
Phase B1 (FEATURES3) — Enhanced deduplication: dual-field matching + normalization.

Responsibilities:
  1. extract_and_link_tags() — given article text + article identity,
     extract 5–8 keyword tags (via LLM or overrides), three-pass fuzzy-match
     against the pre-seeded tag table, create any new tags, and write
     ArticleTag junction rows.
  2. get_articles_by_tag() — return article IDs for a given tag slug.

Design rules enforced here:
  - Max 8 ArticleTag rows per article (lowest-relevance discarded if overflow)
  - Tag names are always lowercase-hyphenated ("nuclear-energy", "article-370")
  - Existing tags are REUSED via three-pass matching (difflib, threshold 0.75):
      Pass 1: exact slug  →  Pass 2: exact name  →  Pass 3: fuzzy slug + normalized slug
  - Normalization strips filler words ("of", "india", "act", etc.) before fuzzy compare,
    so "constitution-of-india" correctly matches "indian-constitution"
  - New tags are created only when all 3 passes fail — 1 extra GROQ call for description
  - usage_count on Tag incremented atomically via F() on every new ArticleTag
  - All exceptions captured to Sentry + structlog; never propagated to caller
"""

import difflib
import json
import re
from typing import Optional
from uuid import UUID

import sentry_sdk
import structlog
from django.db import transaction
from django.db.models import F
from django.utils.text import slugify

from engines.book_content.services.llm_service import llm_call
from engines.tags.models import (
    ARTICLE_CONTENT_TYPE_CHOICES,
    TAG_TYPE_CHOICES,
    ArticleTag,
    Tag,
)

logger = structlog.get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_TAGS_PER_ARTICLE = 8
FUZZY_THRESHOLD = 0.85  # Phase D: raised from 0.75 — prevents false positives like
# hindi→india, culture→agriculture, article-324→article-81

VALID_CONTENT_TYPES = {c[0] for c in ARTICLE_CONTENT_TYPE_CHOICES}
VALID_TAG_TYPES = {t[0] for t in TAG_TYPE_CHOICES}

# ── Normalisation helpers ─────────────────────────────────────────────────────
# Words that do NOT carry semantic meaning for slug-matching purposes.
# Stripped before fuzzy comparison to collapse near-duplicate tags across
# all four GS subject areas:
#
#   GS1 (History/Geography/Culture/Society):
#     "world-history" → "history"
#     "ancient-indian-culture" → "ancient-culture"
#     "physical-geography-of-india" → "physical-geography"
#
#   GS2 (Polity/Governance/IR):
#     "election-commission-of-india" → "election-commission"
#     "standing-committee-on-finance" → "standing-finance"
#     "ministry-of-external-affairs" → "external-affairs"
#     "bilateral-relations-india-us" → "bilateral-us"
#
#   GS3 (Economy/S&T/Environment/Security/Disaster):
#     "pm-kisan-scheme" → "pm-kisan"
#     "jal-jeevan-mission" → "jal-jeevan"
#     "national-disaster-management-authority" → "disaster"
#     "department-of-space" → "space"
#
#   GS4 (Ethics/Integrity/Aptitude):
#     "national-human-rights-commission" → "human-rights"
#     "central-vigilance-commission" → "vigilance"
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

    Numeric slugs like "article-324", "schedule-7", "section-144", "rti-2005"
    must NEVER be fuzzy-matched — even high similarity scores produce wrong
    matches (article-324 → article-81, rti-2005 → rti-1923, etc.).
    Exact slug or name match (Pass 1 / Pass 2) is the only safe path for these.
    """
    return any(ch.isdigit() for ch in slug)


def _normalize_for_match(text: str) -> str:
    """
    Strips filler words and normalises to lowercase hyphenated form.
    Used for fuzzy matching only — NOT for slug generation.
    Falls back to the original text if all words are stripped (prevents empty keys).

    Examples (covering all GS subject domains):
      GS1: "physical-geography-of-india"      → "physical-geography"
      GS1: "ancient-indian-culture"           → "ancient-culture"
      GS2: "election-commission-of-india"     → "election"
      GS2: "ministry-of-external-affairs"     → "external-affairs"
      GS3: "pm-kisan-scheme"                  → "pm-kisan"
      GS3: "jal-jeevan-mission"               → "jal-jeevan"
      GS3: "national-disaster-management-authority" → "disaster"
      GS4: "central-vigilance-commission"     → "vigilance"
    """
    words = re.split(r"[-\s]+", text.lower().strip())
    filtered = [w for w in words if w and w not in _FILLER_WORDS]
    return "-".join(filtered) if filtered else text.lower()


# ── Prompts ───────────────────────────────────────────────────────────────────
_EXTRACT_TAGS_PROMPT = """You are a knowledge platform keyword tagger. Extract EXACTLY 5 to 8 important keyword tags from the article below.

Return ONLY a valid JSON array — no extra text, no markdown fences.
Format: [{{"name": "keyword-name", "type": "topic", "relevance": 1.0}}, ...]

Rules for "name":
- Lowercase-hyphenated (e.g. "nuclear-energy", "article-370", "pm-kisan")
- Specific and discoverable — avoid bare words like "india", "government", "policy", "issue"
- Each tag must be a distinct, meaningful discovery label for the article
- MINIMUM 5 tags required — if fewer are obvious, add relevant subject-area tags

Allowed "type" values (pick the best fit):
topic | subtopic | scheme | person | place | organisation | concept | law | event | other

"relevance": float 0.0–1.0 (1.0 = primary tag, lower = secondary)

Article (first 3000 chars):
{article_text}

Return JSON array only:"""

_NEW_TAG_DESCRIPTION_PROMPT = """You are a concise encyclopaedic reference writer.
Write a single sentence (max 20 words) defining what "{tag_name}" is.
Do NOT mention UPSC, exam, aspirants, or GS paper.
Return ONLY the sentence — no quotes, no extra text."""


# ── Main Service ──────────────────────────────────────────────────────────────
class TagService:
    """
    Keyword tag extraction and linking service.

    Usage:
        tags = TagService.extract_and_link_tags(
            article_text=article.body_md,
            content_type="daily_ca",
            object_id=article.id,
        )
    """

    # ── Public API ─────────────────────────────────────────────────────────────

    @classmethod
    def extract_and_link_tags(
        cls,
        article_text: str,
        content_type: str,
        object_id: UUID,
        overrides: Optional[list[str]] = None,
        db_alias: str = "default",
    ) -> list[Tag]:
        """
        Extract and link keyword tags to an article.

        Args:
            article_text:  Full article markdown text.
            content_type:  "daily_ca" or "book_content".
            object_id:     UUID primary key of the article.
            overrides:     Optional list of raw keyword strings from the LLM
                           TAGS: line (e.g. ["nuclear energy", "Article 370"]).
                           When provided, skips the GROQ extraction call.
            db_alias:      Django database alias (default: "default").

        Returns:
            List of Tag objects that were linked. Empty list on failure.
        """
        if content_type not in VALID_CONTENT_TYPES:
            logger.error(
                "tag_service_invalid_content_type",
                content_type=content_type,
                object_id=str(object_id),
            )
            return []

        try:
            # Step 1: Get raw keyword candidates
            candidates = cls._get_candidates(article_text, overrides)
            if not candidates:
                logger.warning(
                    "tag_service_no_candidates",
                    content_type=content_type,
                    object_id=str(object_id),
                )
                return []

            # Step 2: Resolve each candidate → Tag (reuse or create)
            resolved: list[tuple[Tag, float]] = []  # (tag, relevance)
            for candidate in candidates:
                tag = cls._resolve_or_create_tag(candidate, db_alias=db_alias)
                if tag:
                    resolved.append((tag, candidate.get("relevance", 1.0)))

            if not resolved:
                return []

            # Step 3: Deduplicate (same tag appearing twice from different candidates)
            seen_ids: set = set()
            unique_resolved: list[tuple[Tag, float]] = []
            for tag, relevance in resolved:
                if tag.pk not in seen_ids:
                    seen_ids.add(tag.pk)
                    unique_resolved.append((tag, relevance))

            # Step 4: Enforce max 8 — sort by relevance desc, keep top 8
            unique_resolved.sort(key=lambda x: x[1], reverse=True)
            final = unique_resolved[:MAX_TAGS_PER_ARTICLE]

            # Step 5: Write ArticleTag rows + increment usage_count
            linked = cls._create_article_tags(
                final, content_type, object_id, db_alias=db_alias
            )

            logger.info(
                "tag_service_linked",
                content_type=content_type,
                object_id=str(object_id),
                count=len(linked),
                tags=[t.name for t in linked],
            )
            return linked

        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error(
                "tag_service_extract_failed",
                content_type=content_type,
                object_id=str(object_id),
                error=str(exc)[:200],
            )
            return []

    @classmethod
    def get_articles_by_tag(
        cls,
        tag_slug: str,
        content_type: Optional[str] = None,
        limit: int = 20,
    ) -> list[UUID]:
        """
        Return article IDs carrying a given tag, newest first.

        Args:
            tag_slug:     URL slug of the tag.
            content_type: Optional filter ("daily_ca" or "book_content").
            limit:        Max results (default 20).

        Returns:
            List of article UUIDs.
        """
        try:
            tag = Tag.objects.filter(slug=tag_slug, is_active=True).first()
            if not tag:
                logger.warning("tag_service_tag_not_found", slug=tag_slug)
                return []

            qs = ArticleTag.objects.filter(tag=tag)
            if content_type:
                qs = qs.filter(content_type=content_type)

            return list(
                qs.order_by("-created_at").values_list("object_id", flat=True)[:limit]
            )

        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error(
                "tag_service_get_articles_failed",
                slug=tag_slug,
                error=str(exc)[:200],
            )
            return []

    # ── Private Helpers ────────────────────────────────────────────────────────

    @classmethod
    def _get_candidates(
        cls,
        article_text: str,
        overrides: Optional[list[str]],
    ) -> list[dict]:
        """
        Build the list of keyword candidates as dicts with name/type/relevance.

        If overrides are provided, convert raw strings → normalized dicts.
        Otherwise call GROQ to extract from article text.
        """
        if overrides:
            candidates = []
            for i, raw in enumerate(overrides[:MAX_TAGS_PER_ARTICLE]):
                name = cls._normalize_tag_name(raw)
                if name:
                    candidates.append(
                        {
                            "name": name,
                            "type": "topic",  # safe default; will be overridden if matched
                            "relevance": round(1.0 - (i * 0.05), 2),
                        }
                    )
            return candidates

        # GROQ extraction call
        prompt = _EXTRACT_TAGS_PROMPT.format(article_text=article_text[:3000])
        raw_response = llm_call(prompt, mode="standard")

        if not raw_response:
            logger.warning("tag_service_llm_empty_response")
            return []

        return cls._parse_llm_response(raw_response)

    @classmethod
    def _parse_llm_response(cls, raw: str) -> list[dict]:
        """Parse JSON array from LLM response. Robust to minor formatting issues."""
        try:
            # Strip markdown fences if present
            cleaned = re.sub(r"```(?:json)?", "", raw).strip()
            # Extract first JSON array
            match = re.search(r"\[.*\]", cleaned, re.DOTALL)
            if not match:
                logger.warning("tag_service_no_json_array", raw=raw[:100])
                return []

            data = json.loads(match.group())
            candidates = []
            for item in data:
                if not isinstance(item, dict) or "name" not in item:
                    continue
                name = cls._normalize_tag_name(item["name"])
                if not name:
                    continue
                tag_type = item.get("type", "topic")
                if tag_type not in VALID_TAG_TYPES:
                    tag_type = "topic"
                relevance = float(item.get("relevance", 1.0))
                relevance = max(0.0, min(1.0, relevance))
                candidates.append(
                    {
                        "name": name,
                        "type": tag_type,
                        "relevance": relevance,
                    }
                )
            return candidates

        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "tag_service_json_parse_error",
                error=str(exc),
                raw=raw[:200],
            )
            return []

    @classmethod
    def _resolve_or_create_tag(
        cls, candidate: dict, db_alias: str = "default"
    ) -> Optional[Tag]:
        """
        Phase B1 — Three-pass tag resolution with normalized fuzzy matching.

        Find an existing Tag or create a new one. Resolution order:
          Pass 1: Exact slug match (fastest, zero false positives)
          Pass 2: Exact name match (case-insensitive, catches spacing/case variants)
          Pass 3a: Fuzzy match on raw slug (threshold 0.75)
          Pass 3b: Fuzzy match on normalized slug — strips filler words so
                   "constitution-of-india" correctly matches "indian-constitution"
        Creates a new tag with GROQ-generated description only when all passes fail.
        Returns None on failure.
        """
        name: str = candidate["name"]
        tag_type: str = candidate["type"]
        slug = slugify(name)

        try:
            # Pass 1: exact slug
            tag = Tag.objects.using(db_alias).filter(slug=slug, is_active=True).first()
            if tag:
                return tag

            # Pass 2: exact name match (case-insensitive)
            tag = (
                Tag.objects.using(db_alias)
                .filter(name__iexact=slug.replace("-", " "), is_active=True)
                .first()
            )
            if tag:
                logger.info(
                    "tag_service_name_match",
                    input_slug=slug,
                    matched_name=tag.name,
                )
                return tag

            # Pass 3: load all active slugs once, then try fuzzy variants
            all_tags_qs = list(
                Tag.objects.using(db_alias).filter(is_active=True).values("slug")
            )
            if not all_tags_qs:
                return cls._create_new_tag(name, slug, tag_type, db_alias=db_alias)

            all_slugs = [t["slug"] for t in all_tags_qs]

            # Pass 3a: fuzzy on raw slug
            # Numeric slugs (article-324, schedule-7, rti-2005 …) must NEVER fuzzy-match —
            # digits encode the exact identity of the law/article; fuzzy scores are
            # misleading (article-324 ≈ article-81 at high similarity). Skip to creation.
            if not _slug_has_digits(slug):
                matches = difflib.get_close_matches(
                    slug, all_slugs, n=1, cutoff=FUZZY_THRESHOLD
                )
                if matches:
                    tag = Tag.objects.using(db_alias).get(slug=matches[0])
                    logger.info(
                        "tag_service_fuzzy_match",
                        input_slug=slug,
                        matched_slug=matches[0],
                    )
                    return tag

            # Pass 3b: fuzzy on normalized slug (strips filler words)
            # Also skipped for numeric slugs — same rationale as Pass 3a.
            if not _slug_has_digits(slug):
                norm_slug = _normalize_for_match(slug)
                norm_map = {_normalize_for_match(s): s for s in all_slugs}
                norm_matches = difflib.get_close_matches(
                    norm_slug, list(norm_map.keys()), n=1, cutoff=FUZZY_THRESHOLD
                )
                if norm_matches:
                    original_slug = norm_map[norm_matches[0]]
                    tag = Tag.objects.using(db_alias).get(slug=original_slug)
                    logger.info(
                        "tag_service_normalized_fuzzy_match",
                        input_slug=slug,
                        normalized_input=norm_slug,
                        matched_slug=original_slug,
                    )
                    return tag

            # All passes failed — create new tag with LLM-generated description
            return cls._create_new_tag(name, slug, tag_type, db_alias=db_alias)

        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error(
                "tag_service_resolve_failed",
                name=name,
                error=str(exc)[:200],
            )
            return None

    @classmethod
    def _create_new_tag(
        cls, name: str, slug: str, tag_type: str, db_alias: str = "default"
    ) -> Optional[Tag]:
        """
        Create a brand-new Tag row with a GROQ-generated description.
        Rate-limited by INTER_CALL_SLEEP from llm_service.
        """
        try:
            prompt = _NEW_TAG_DESCRIPTION_PROMPT.format(tag_name=name)
            description = llm_call(prompt, mode="standard").strip()

            # Trim to reasonable length
            if len(description) > 200:
                description = description[:197] + "..."

            tag = Tag.objects.using(db_alias).create(
                name=name,
                slug=slug,
                tag_type=tag_type,
                description=description,
                is_active=True,
                usage_count=0,
            )
            logger.info(
                "tag_service_new_tag_created",
                name=name,
                slug=slug,
                tag_type=tag_type,
            )
            return tag

        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error(
                "tag_service_create_failed",
                name=name,
                slug=slug,
                error=str(exc)[:200],
            )
            return None

    @classmethod
    def _create_article_tags(
        cls,
        resolved: list[tuple[Tag, float]],
        content_type: str,
        object_id: UUID,
        db_alias: str = "default",
    ) -> list[Tag]:
        """
        Write ArticleTag rows atomically.
        Increments Tag.usage_count for each new link.
        Skips rows that already exist (get_or_create).
        """
        linked: list[Tag] = []
        with transaction.atomic(using=db_alias):
            for tag, relevance in resolved:
                article_tag, created = ArticleTag.objects.using(db_alias).get_or_create(
                    tag=tag,
                    content_type=content_type,
                    object_id=object_id,
                    defaults={"relevance": relevance},
                )
                if created:
                    # Increment usage_count atomically
                    Tag.objects.using(db_alias).filter(pk=tag.pk).update(
                        usage_count=F("usage_count") + 1
                    )
                    logger.info(
                        "tag_service_article_tag_created",
                        tag=tag.name,
                        content_type=content_type,
                        object_id=str(object_id),
                    )
                linked.append(tag)
        return linked

    @staticmethod
    def _normalize_tag_name(raw: str) -> str:
        """
        Normalize a raw keyword to lowercase-hyphenated form.
        e.g. "Nuclear Energy"  → "nuclear-energy"
             "Article  370"    → "article-370"
             "PM-KISAN scheme" → "pm-kisan-scheme"
        Returns empty string if result is blank.
        """
        normalized = slugify(raw.strip().lower())
        return normalized
