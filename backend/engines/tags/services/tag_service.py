"""
engines/tags/services/tag_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase E1 — TagService: Keyword Tag extraction and linking.

Responsibilities:
  1. extract_and_link_tags() — given article text + article identity,
     extract 5–8 UPSC keyword tags (via LLM or overrides), fuzzy-match
     against the pre-seeded tag table, create any new tags, and write
     ArticleTag junction rows.
  2. get_articles_by_tag() — return article IDs for a given tag slug.

Design rules enforced here:
  - Max 8 ArticleTag rows per article (lowest-relevance discarded if overflow)
  - Tag names are always lowercase-hyphenated ("nuclear-energy", "article-370")
  - Existing tags are REUSED via fuzzy slug match (difflib, threshold 0.85)
  - New tags are created only when no match exists — 1 extra GROQ call for description
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
FUZZY_THRESHOLD = 0.85

VALID_CONTENT_TYPES = {c[0] for c in ARTICLE_CONTENT_TYPE_CHOICES}
VALID_TAG_TYPES = {t[0] for t in TAG_TYPE_CHOICES}


# ── Prompts ───────────────────────────────────────────────────────────────────
_EXTRACT_TAGS_PROMPT = """You are a UPSC keyword tagger. Extract 5–8 important keyword tags from the article below.

Return ONLY a valid JSON array — no extra text, no markdown fences.
Format: [{{"name": "keyword-name", "type": "topic", "relevance": 1.0}}, ...]

Rules for "name":
- Lowercase-hyphenated (e.g. "nuclear-energy", "article-370", "pm-kisan")
- Specific, not generic — avoid "india", "government", "policy", "issue"
- Must be findable in a UPSC study index

Allowed "type" values (pick the best fit):
topic | subtopic | scheme | person | place | organisation | concept | law | event | other

"relevance": float 0.0–1.0 (1.0 = primary tag, lower = secondary)

Article (first 3000 chars):
{article_text}

Return JSON array only:"""

_NEW_TAG_DESCRIPTION_PROMPT = """You are a UPSC content expert.
Write a single concise sentence (max 20 words) describing what "{tag_name}" means in the UPSC context.
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
        Find an existing Tag via exact slug or fuzzy match.
        If no match found: create a new Tag with a GROQ-generated description.
        Returns None on failure.
        """
        name: str = candidate["name"]
        tag_type: str = candidate["type"]
        slug = slugify(name)

        try:
            # 1. Exact slug match
            tag = Tag.objects.using(db_alias).filter(slug=slug, is_active=True).first()
            if tag:
                return tag

            # 2. Fuzzy slug match (difflib against all active slugs)
            all_slugs = list(
                Tag.objects.using(db_alias)
                .filter(is_active=True)
                .values_list("slug", flat=True)
            )
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

            # 3. No match — create new tag with LLM-generated description
            tag = cls._create_new_tag(name, slug, tag_type, db_alias=db_alias)
            return tag

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
