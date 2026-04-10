"""
engines/daily_ca/services/static_background_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase G — StaticBackgroundService

Two responsibilities:
  1. get_background_facts(topic_id)
       Called INSIDE each CA generation cycle.
       Checks if published static content exists → returns structured facts INSTANTLY.
       NEVER blocks. NEVER generates. NEVER polls. Returns None immediately if absent.

  2. trigger_pending_static_generation(topic_ids)
       Called ONCE after ALL CA cycles complete.
       Fire-and-forget POST to book_content internal endpoint for each topic.
       Does NOT wait for generation — 202 Accepted and move on.

Architecture: CA-First, Static-Background
  Day 1: no static → cycle proceeds with wiki enrichment → topic queued
  Post-cycle: background static generation triggered for queued topics
  Day 2+: static exists → used as factual anchor in future CA articles

NEVER makes direct Django ORM calls to book_content tables.
All book_content access is via internal HTTP API only.
"""

import re
import time
from typing import Optional
from uuid import UUID

import requests
import sentry_sdk
import structlog
from django.conf import settings

logger = structlog.get_logger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
# Base URL for internal API calls. Override in settings for production.
# Local dev: http://127.0.0.1:8000
# Render production: set INTERNAL_API_BASE_URL in environment variables.
_INTERNAL_API_BASE = getattr(settings, "INTERNAL_API_BASE_URL", "http://127.0.0.1:8000")

# Timeout for the GET check (should be very fast — DB lookup only)
_GET_TIMEOUT_SECONDS = 10

# Sleep between trigger POSTs — respects book_content GROQ rate limits (12s)
_TRIGGER_SLEEP_SECONDS = 12


# ── Fact extraction patterns ──────────────────────────────────────────────────
# Ordered from most specific to most general.
# Each tuple: (pattern, label_prefix)
_FACT_PATTERNS = [
    # Article / Section numbers: "Article 21", "Section 66A", "Article 370(3)"
    (re.compile(r"\bArticle\s+\d+[\w()]*\b"), "article"),
    (re.compile(r"\bSection\s+\d+[\w()]*\b"), "section"),
    # Amendment numbers: "42nd Amendment", "101st Constitutional Amendment"
    (re.compile(r"\b\d{1,3}(?:st|nd|rd|th)\s+(?:Constitutional\s+)?Amendment\b"), "amendment"),
    # Percentages: "35%", "35 percent"
    (re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|percent)\b"), "statistic"),
    # Monetary figures: "₹500 crore", "Rs 1000 crore", "$10 billion"
    (re.compile(r"(?:₹|Rs\.?\s*|USD?\s*|INR\s*)\d[\d,]*(?:\.\d+)?\s*(?:crore|lakh|billion|million|thousand)?\b", re.IGNORECASE), "figure"),
    # Key years: standalone 4-digit years 1947–2030
    (re.compile(r"\b(19[4-9]\d|20[0-3]\d)\b"), "year"),
    # "Established in YYYY", "Founded in YYYY", "Enacted in YYYY"
    (re.compile(r"\b(?:established|founded|enacted|passed|notified|constituted)\s+in\s+\d{4}\b", re.IGNORECASE), "date_fact"),
    # Target numbers: "target of 500 GW", "capacity of 40,000 MW"
    (re.compile(r"\b(?:target|capacity|goal)\s+of\s+[\d,]+\s*\w+\b", re.IGNORECASE), "target"),
]

# Bullet / numbered list lines — capture content after "- " or "N. "
_BULLET_LINE = re.compile(r"^\s*(?:[-*•]|\d+\.)\s+(.+)$", re.MULTILINE)


def _extract_facts_from_content(content_markdown: str) -> dict:
    """
    Extracts structured key facts from published BookContent markdown.

    Pure Python regex — zero GROQ calls, runs instantly.

    Extraction logic:
      key_facts       — bullet/numbered list items (max 10, from first 3000 chars)
      key_provisions  — Article/Section/Amendment references found anywhere in text
      statistics      — percentages, monetary figures, year facts

    Returns dict with three lists:
      {
        "key_provisions": ["Article 21 guarantees right to life", ...],
        "key_facts":      ["Established in 1950", "Covers 28 states", ...],
        "statistics":     ["35%", "₹500 crore", ...],
      }
    """
    # Work on first 4000 chars — factual anchors live in intro/provisions sections
    text = content_markdown[:4000]

    # ── key_facts: bullet/numbered list items ─────────────────────────────────
    key_facts: list[str] = []
    for match in _BULLET_LINE.finditer(text):
        line = match.group(1).strip()
        # Skip very short or heading-like lines
        if len(line) > 15 and not line.startswith("#"):
            key_facts.append(line[:200])
        if len(key_facts) >= 10:
            break

    # ── key_provisions: Article/Section/Amendment references ──────────────────
    # Extract sentence containing each provision reference (more context = better anchor)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    key_provisions: list[str] = []
    seen_provisions: set[str] = set()

    article_pat = re.compile(r"\b(?:Article|Section)\s+\d+|Amendment\b", re.IGNORECASE)
    for sentence in sentences:
        if article_pat.search(sentence):
            clean = sentence.strip()[:250]
            if clean not in seen_provisions and len(clean) > 20:
                key_provisions.append(clean)
                seen_provisions.add(clean)
        if len(key_provisions) >= 8:
            break

    # ── statistics: percentages, figures, year facts ──────────────────────────
    statistics: list[str] = []
    seen_stats: set[str] = set()
    for pattern, _ in _FACT_PATTERNS[3:]:  # patterns from index 3 onward are stats
        for match in pattern.finditer(text):
            val = match.group(0).strip()
            if val not in seen_stats:
                seen_stats.add(val)
                statistics.append(val)
        if len(statistics) >= 10:
            break

    return {
        "key_provisions": key_provisions,
        "key_facts": key_facts,
        "statistics": statistics[:10],
    }


# ── Main Service ──────────────────────────────────────────────────────────────


class StaticBackgroundService:
    """
    Manages static BookContent lookup and background generation triggering.

    Usage inside _run_single_cycle():
        static_facts = StaticBackgroundService.get_background_facts(proposal.topic_id)
        if static_facts is None:
            needs_static = True   # will be triggered post-cycle

    Usage after all cycles complete:
        triggered = StaticBackgroundService.trigger_pending_static_generation(topic_ids)
    """

    @staticmethod
    def get_background_facts(topic_id: Optional[UUID]) -> Optional[dict]:
        """
        Checks if published static BookContent exists for a topic.
        Returns structured facts INSTANTLY — NEVER blocks, NEVER generates, NEVER waits.

        Case A: GET returns 200 + is_published=True
                → extract key facts via regex → return dict
                → dict keys: title, key_provisions, key_facts, statistics, book_content_id

        Case B: GET returns 404 or empty list
                → return None immediately (caller queues topic for post-cycle trigger)

        Case C: GET returns 200 + is_published=False
                → return None immediately (draft content — do not use as anchor)

        Returns None on any network error or exception (fail-safe — never breaks CA cycle).
        """
        if not topic_id:
            return None

        try:
            url = f"{_INTERNAL_API_BASE}/api/v1/book/content/{topic_id}/"
            response = requests.get(url, timeout=_GET_TIMEOUT_SECONDS)

            # Case B: no static content exists
            if response.status_code == 404:
                logger.debug(
                    "static_background_not_found",
                    topic_id=str(topic_id),
                )
                return None

            if response.status_code != 200:
                logger.warning(
                    "static_background_unexpected_status",
                    topic_id=str(topic_id),
                    http_status=response.status_code,
                )
                return None

            data = response.json()

            # Case C: exists but not published (draft/incomplete)
            if not data.get("is_published", False):
                logger.debug(
                    "static_background_not_published",
                    topic_id=str(topic_id),
                    topic_name=data.get("topic_name", ""),
                )
                return None

            # Case A: published static exists — extract structured facts
            content_markdown = data.get("content_markdown", "")
            facts = _extract_facts_from_content(content_markdown)
            facts["title"] = data.get("topic_name", "")
            facts["book_content_id"] = data.get("id")

            logger.info(
                "static_background_found",
                topic_id=str(topic_id),
                topic_name=facts["title"],
                provisions=len(facts["key_provisions"]),
                bullet_facts=len(facts["key_facts"]),
                statistics=len(facts["statistics"]),
            )
            return facts

        except requests.exceptions.Timeout:
            # Timeout on the static check — return None, CA cycle continues normally
            logger.warning(
                "static_background_get_timeout",
                topic_id=str(topic_id),
                timeout=_GET_TIMEOUT_SECONDS,
            )
            return None

        except requests.exceptions.ConnectionError:
            # Server not reachable — expected in test/offline environments
            logger.warning(
                "static_background_connection_error",
                topic_id=str(topic_id),
            )
            return None

        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error(
                "static_background_get_failed",
                topic_id=str(topic_id),
                error=str(exc),
            )
            return None

    @staticmethod
    def trigger_pending_static_generation(topic_ids: list) -> int:
        """
        Fires background static generation for topics that had no published static.
        Called ONCE after ALL CA cycles complete — NOT inside individual cycles.

        For each topic_id:
          → POST /api/v1/book/internal/generate/{topic_id}/
          → 202 Accepted: book_content engine starts ingest_topic() in a daemon thread
          → Does NOT wait for completion (fire-and-forget)
          → 12s sleep between each POST to avoid hammering GROQ rate limits on book_content side
          → Skips topics that are already published (202 returns "already_exists" → still counted)

        Returns: count of successfully triggered (202 or 200) POSTs.
        Errors for individual topics are logged + Sentry-captured but never raise.
        """
        if not topic_ids:
            logger.debug("static_trigger_no_topics")
            return 0

        triggered = 0

        for i, topic_id in enumerate(topic_ids):
            if not topic_id:
                continue
            try:
                url = f"{_INTERNAL_API_BASE}/api/v1/book/internal/generate/{topic_id}/"
                response = requests.post(url, timeout=_GET_TIMEOUT_SECONDS)

                if response.status_code in (200, 202):
                    result_status = response.json().get("status", "unknown")
                    logger.info(
                        "static_trigger_success",
                        topic_id=str(topic_id),
                        result=result_status,
                        index=i + 1,
                        total=len(topic_ids),
                    )
                    triggered += 1
                else:
                    logger.warning(
                        "static_trigger_unexpected_status",
                        topic_id=str(topic_id),
                        http_status=response.status_code,
                    )

            except requests.exceptions.Timeout:
                logger.warning(
                    "static_trigger_timeout",
                    topic_id=str(topic_id),
                )

            except requests.exceptions.ConnectionError:
                logger.warning(
                    "static_trigger_connection_error",
                    topic_id=str(topic_id),
                )

            except Exception as exc:
                sentry_sdk.capture_exception(exc)
                logger.error(
                    "static_trigger_failed",
                    topic_id=str(topic_id),
                    error=str(exc),
                )

            # Rate-limit guard: sleep between POSTs so book_content's GROQ calls
            # don't collide if multiple background threads start close together.
            # Skip sleep after last item.
            if i < len(topic_ids) - 1:
                time.sleep(_TRIGGER_SLEEP_SECONDS)

        logger.info(
            "static_trigger_complete",
            triggered=triggered,
            total=len(topic_ids),
        )
        return triggered
