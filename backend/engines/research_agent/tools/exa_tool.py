"""
engines/research_agent/tools/exa_tool.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ExaTool — secondary search provider (neural search).

Activated when Tavily fails or hits monthly quota.
Same hard limits as Tavily:
  - MAX 3 results per query
  - Content truncated to MAX 400 chars
  - Unicode normalization on all text

On any failure → raises SearchToolError → Search Agent falls back to WikipediaTool.
"""

from __future__ import annotations

import unicodedata
import structlog
import sentry_sdk
from django.conf import settings

from engines.research_agent.tools.tavily_tool import SearchToolError

logger = structlog.get_logger(__name__)

MAX_RESULTS = 3
MAX_CONTENT_CHARS = 800  # deeper content → richer, better-grounded synthesis


class ExaTool:
    """
    Fallback search using Exa's neural search API.
    Uses highlights (sentence-level excerpts) as content — more precise than
    full-page content for UPSC fact-dense queries.

    Returns same dict shape as TavilyTool: [{url, title, content, score, source}]
    """

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        """Lazy-initialize Exa client."""
        if self._client is not None:
            return self._client

        api_key = getattr(settings, "EXA_API_KEY", None)
        if not api_key:
            raise SearchToolError(
                "EXA_API_KEY not configured. Falling back to Wikipedia."
            )

        try:
            from exa_py import Exa

            self._client = Exa(api_key=api_key)
            return self._client
        except ImportError:
            raise SearchToolError("exa-py not installed. Falling back to Wikipedia.")

    def search(self, query: str) -> list[dict]:
        """
        Execute neural search via Exa API.

        Args:
            query: The search query string.

        Returns:
            List of dicts with keys: url, title, content, score, source

        Raises:
            SearchToolError: On any failure — triggers Wikipedia fallback.
        """
        try:
            client = self._get_client()

            logger.info(
                "research_agent.exa.search_start",
                query=query[:100],
            )

            # NOTE: exa-py >= 2.x removed `use_autoprompt`; the replacement is
            # `type="auto"` (Exa picks neural vs keyword automatically). Passing
            # the old kwarg raises "Invalid option: 'use_autoprompt'" → Exa always
            # failed and the chain silently skipped to Wikipedia.
            response = client.search_and_contents(
                query,
                num_results=MAX_RESULTS,
                highlights={"num_sentences": 3, "highlights_per_url": 1},
                type="auto",
            )

            results = self._parse_results(response)

            logger.info(
                "research_agent.exa.search_complete",
                query=query[:100],
                result_count=len(results),
            )

            return results

        except SearchToolError:
            raise
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.warning(
                "research_agent.exa.search_failed",
                query=query[:100],
                error=str(exc),
            )
            raise SearchToolError(f"Exa search failed: {exc}") from exc

    def _parse_results(self, response) -> list[dict]:
        """
        Normalizes Exa response into standard format.
        Prefers highlights over full text — shorter, more relevant excerpts.
        """
        results = []
        raw_results = getattr(response, "results", [])

        for item in raw_results[:MAX_RESULTS]:
            # Prefer highlights (sentence-level) over full text
            highlights = getattr(item, "highlights", None) or []
            if highlights:
                content = " ".join(highlights)
            else:
                content = getattr(item, "text", "") or ""

            content = self._normalize_text(content)[:MAX_CONTENT_CHARS]
            title = self._normalize_text(getattr(item, "title", "") or "")
            url = getattr(item, "url", "") or ""

            if not url:
                continue

            results.append(
                {
                    "url": url,
                    "title": title,
                    "content": content,
                    "score": round(float(getattr(item, "score", 0.0) or 0.0), 4),
                    "source": "exa",
                }
            )

        return results

    def _normalize_text(self, text: str) -> str:
        """NFC Unicode normalization — handles Hindi/Arabic/emoji safely (Risk #47)."""
        if not text:
            return ""
        return unicodedata.normalize("NFC", text)
