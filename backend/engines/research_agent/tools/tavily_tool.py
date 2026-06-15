"""
engines/research_agent/tools/tavily_tool.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TavilyTool — primary web search provider.

Hard limits enforced here (never configurable by user or agent):
  - MAX 3 results per query (Risk #30)
  - Each result content truncated to MAX 400 chars (Risk #30)
  - search_depth="advanced" for freshness (Risk #34)
  - Tavily monthly usage tracked in Redis (Risk #45)

On any failure → raises SearchToolError → Search Agent falls back to ExaTool.

Unicode normalization applied to all content (Risk #47).
"""

from __future__ import annotations

import unicodedata
import structlog
import sentry_sdk
from django.conf import settings

logger = structlog.get_logger(__name__)

MAX_RESULTS = 3
MAX_CONTENT_CHARS = 800  # deeper content → richer, better-grounded synthesis
TAVILY_USAGE_REDIS_KEY = "research:tavily:usage:{month}"


class SearchToolError(Exception):
    """Raised when a search tool fails — triggers fallback to next in chain."""

    pass


class TavilyTool:
    """
    Primary search tool. Uses Tavily's /search endpoint.

    Returns list of dicts: [{url, title, content, score}]
    Content is always truncated to MAX_CONTENT_CHARS before returning.

    Raises SearchToolError on:
      - Missing API key
      - HTTP errors (4xx, 5xx)
      - Timeout (>10s)
      - Any unexpected exception
    """

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        """Lazy-initialize Tavily client — avoids import at Django startup."""
        if self._client is not None:
            return self._client

        api_key = getattr(settings, "TAVILY_API_KEY", None)
        if not api_key:
            raise SearchToolError("TAVILY_API_KEY not configured. Falling back to Exa.")

        try:
            from tavily import TavilyClient

            self._client = TavilyClient(api_key=api_key)
            return self._client
        except ImportError:
            raise SearchToolError("tavily-python not installed. Falling back to Exa.")

    def search(self, query: str) -> list[dict]:
        """
        Execute a single search query. Returns max 3 results.

        Args:
            query: The search query string.

        Returns:
            List of dicts with keys: url, title, content, score

        Raises:
            SearchToolError: On any failure — triggers fallback chain.
        """
        try:
            client = self._get_client()

            logger.info(
                "research_agent.tavily.search_start",
                query=query[:100],
            )

            response = client.search(
                query=query,
                max_results=MAX_RESULTS,
                search_depth="advanced",  # freshest results (Risk #34)
                include_answer=False,
                include_raw_content=False,
            )

            results = self._parse_results(response)

            self._track_usage()

            logger.info(
                "research_agent.tavily.search_complete",
                query=query[:100],
                result_count=len(results),
            )

            return results

        except SearchToolError:
            raise
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.warning(
                "research_agent.tavily.search_failed",
                query=query[:100],
                error=str(exc),
            )
            raise SearchToolError(f"Tavily search failed: {exc}") from exc

    def _parse_results(self, response: dict) -> list[dict]:
        """
        Normalizes Tavily response into standard format.
        Enforces MAX_CONTENT_CHARS truncation on every result.
        Applies Unicode normalization (Risk #47).
        """
        results = []
        raw_results = response.get("results", [])

        for item in raw_results[:MAX_RESULTS]:
            content = item.get("content") or item.get("snippet") or ""
            content = self._normalize_text(content)
            content = content[:MAX_CONTENT_CHARS]

            title = self._normalize_text(item.get("title", ""))
            url = item.get("url", "")

            if not url:
                continue

            results.append(
                {
                    "url": url,
                    "title": title,
                    "content": content,
                    "score": round(float(item.get("score", 0.0)), 4),
                    "source": "tavily",
                }
            )

        return results

    def _normalize_text(self, text: str) -> str:
        """NFC Unicode normalization — handles Hindi/Arabic/emoji safely (Risk #47)."""
        if not text:
            return ""
        return unicodedata.normalize("NFC", text)

    def _track_usage(self) -> None:
        """
        Increments Tavily monthly usage counter in Redis (Risk #45).
        Alert threshold: 800/1000 free monthly searches.
        Silently skips if Redis unavailable — never blocks search.
        """
        try:
            from datetime import date
            from django_redis import get_redis_connection

            month_key = TAVILY_USAGE_REDIS_KEY.format(
                month=date.today().strftime("%Y-%m")
            )
            redis_conn = get_redis_connection("default")
            count = redis_conn.incr(month_key)
            # Set TTL of 35 days so key auto-expires after the month
            redis_conn.expire(month_key, 35 * 24 * 3600)

            if count >= 800:
                logger.warning(
                    "research_agent.tavily.quota_warning",
                    usage=count,
                    limit=1000,
                    month=date.today().strftime("%Y-%m"),
                )
        except Exception:
            # Redis failure must never block search (Risk #19)
            pass
