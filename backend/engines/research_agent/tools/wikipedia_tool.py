"""
engines/research_agent/tools/wikipedia_tool.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WikipediaTool — last-resort search fallback.

No API key required — always available.
Activated only when both Tavily and Exa fail.

Strategy:
  1. Search Wikipedia for the query (returns candidate page titles)
  2. Fetch summary of the best matching page
  3. Return as standard [{url, title, content, score, source}] dict

Content truncated to MAX 400 chars — same limit as Tavily/Exa.
Returns empty list (not exception) when no Wikipedia article found —
the Search Agent handles empty results gracefully (best-effort report).
"""

from __future__ import annotations

import unicodedata
import structlog
import sentry_sdk

from engines.research_agent.tools.tavily_tool import SearchToolError

logger = structlog.get_logger(__name__)

MAX_RESULTS = 3
MAX_CONTENT_CHARS = 800  # deeper content → richer, better-grounded synthesis
WIKIPEDIA_BASE_URL = "https://en.wikipedia.org/wiki/{}"


class WikipediaTool:
    """
    Last-resort fallback. Uses the `wikipedia` Python package.

    Unlike Tavily/Exa, this tool does NOT raise SearchToolError on a
    'page not found' result — it returns an empty list instead.
    SearchToolError is only raised for hard failures (import error, network error)
    since there is no further fallback after Wikipedia.
    """

    def __init__(self) -> None:
        self._wiki = None

    def _get_wiki(self):
        """Lazy-initialize wikipedia module."""
        if self._wiki is not None:
            return self._wiki
        try:
            import wikipedia

            wikipedia.set_lang("en")
            self._wiki = wikipedia
            return self._wiki
        except ImportError:
            raise SearchToolError(
                "wikipedia package not installed. No further fallback available."
            )

    def search(self, query: str) -> list[dict]:
        """
        Search Wikipedia for the query.

        Returns up to MAX_RESULTS page summaries in standard format.
        Returns empty list if no matching article found — never raises on 404.

        Raises:
            SearchToolError: Only on hard failures (import, network error).
        """
        try:
            wiki = self._get_wiki()

            logger.info(
                "research_agent.wikipedia.search_start",
                query=query[:100],
            )

            # Step 1: get candidate page titles for the query
            titles = wiki.search(query, results=MAX_RESULTS)

            if not titles:
                logger.info(
                    "research_agent.wikipedia.no_results",
                    query=query[:100],
                )
                return []

            results = []
            for title in titles[:MAX_RESULTS]:
                page_result = self._fetch_page(wiki, title, query)
                if page_result:
                    results.append(page_result)

            logger.info(
                "research_agent.wikipedia.search_complete",
                query=query[:100],
                result_count=len(results),
            )

            return results

        except SearchToolError:
            raise
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.warning(
                "research_agent.wikipedia.search_failed",
                query=query[:100],
                error=str(exc),
            )
            raise SearchToolError(f"Wikipedia search failed: {exc}") from exc

    def _fetch_page(self, wiki, title: str, original_query: str) -> dict | None:
        """
        Fetches summary for a single Wikipedia page title.
        Returns None on disambiguation errors or missing pages — skipped silently.
        """
        try:
            page = wiki.page(title, auto_suggest=False)

            content = self._normalize_text(page.summary)[:MAX_CONTENT_CHARS]
            clean_title = self._normalize_text(page.title)
            url = WIKIPEDIA_BASE_URL.format(page.title.replace(" ", "_"))

            return {
                "url": url,
                "title": clean_title,
                "content": content,
                "score": 0.5,  # fixed neutral score — Wikipedia has no relevance ranking
                "source": "wikipedia",
            }

        except Exception:
            # DisambiguationError, PageError, etc. — skip this title, try next
            return None

    def _normalize_text(self, text: str) -> str:
        """NFC Unicode normalization — handles Hindi/Arabic/emoji safely (Risk #47)."""
        if not text:
            return ""
        return unicodedata.normalize("NFC", text)
