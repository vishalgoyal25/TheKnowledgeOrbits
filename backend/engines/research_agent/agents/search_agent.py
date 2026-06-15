"""
engines/research_agent/agents/search_agent.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SearchAgent — the hands, not the brain. NO LLM call (tokens = 0).

Takes the Planner's ≤3 sub-queries and fetches sources for each, then cleans
the pile before any LLM ever sees it. Four jobs:

  1. FAN OUT — run all sub-queries in PARALLEL (threads) for speed.
  2. FALLBACK — per query, walk the chain Tavily → Exa → Wikipedia.
                The first tool that returns results wins; a failure (or empty)
                falls through to the next (circuit breaker, Risk #4/#5).
  3. DEDUPLICATE — the same URL often shows up across sub-queries; keep it once
                   (Risk #31). Also skip URLs already gathered on a prior retry.
  4. SCORE + FILTER — credibility-score every source, drop the junk below
                      threshold, sort best-first so the Research agent's LLM
                      reads the most authoritative sources first.

Why parallel? 3 sub-queries × ~5s each = 15s sequential, but ~5s in parallel.
The searches are I/O-bound HTTP calls, so threads give a clean ~3x speedup.

State fields written (both Annotated[operator.add] → they ACCUMULATE on retry):
  raw_search_results : [{url, title, content, source, credibility_score}]
  sources_used       : [url, ...] (the kept, deduped URLs)
"""

from __future__ import annotations

import concurrent.futures
import structlog

from engines.research_agent.agents.base_agent import BaseAgent
from engines.research_agent.constants import AgentName
from engines.research_agent.graph.state import ResearchState
from engines.research_agent.tools.registry import tool_registry
from engines.research_agent.tools.tavily_tool import SearchToolError

logger = structlog.get_logger(__name__)

# Bounded thread pool — at most 3 sub-queries, so 3 workers is the ceiling.
MAX_SEARCH_WORKERS = 3


class SearchAgent(BaseAgent):
    agent_name = AgentName.SEARCH
    # No LLM call, but keep metadata consistent for the ra_agent_log row.
    model_provider = "groq"
    model_name = "n/a-tool-only"

    def execute(self, state: ResearchState) -> tuple[dict, int]:
        sub_queries = state.get("sub_queries") or []
        if not sub_queries:
            logger.warning(
                "research_agent.search.no_sub_queries",
                session_id=state.get("session_id"),
            )
            return {"raw_search_results": [], "sources_used": []}, 0

        chain = tool_registry.get_search_chain()  # [tavily, exa, wikipedia]

        # ── 1 + 2. Fan out in parallel; each query walks the fallback chain ───
        per_query_results = self._search_all(sub_queries, chain)

        # ── 3. Deduplicate across all sub-queries (and across prior retries) ──
        deduped = self._deduplicate(per_query_results, state)

        # ── 4. Credibility-score, filter junk, sort best-first ────────────────
        scored = tool_registry.get("credibility").score_sources(deduped)

        logger.info(
            "research_agent.search.completed",
            session_id=state.get("session_id"),
            sub_queries=len(sub_queries),
            raw_found=sum(len(r) for r in per_query_results),
            after_dedup=len(deduped),
            after_filter=len(scored),
        )

        partial = {
            "raw_search_results": scored,
            "sources_used": [r["url"] for r in scored],
        }
        return partial, 0

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────────────────────────────────
    def _search_all(self, sub_queries: list[str], chain: list) -> list[list[dict]]:
        """
        Run every sub-query concurrently. Returns a list-of-lists, preserving
        sub-query order so dedup keeps the most-relevant (earliest) source.
        """
        results: list[list[dict]] = [[] for _ in sub_queries]

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_SEARCH_WORKERS
        ) as pool:
            future_to_idx = {
                pool.submit(self._search_one, q, chain): i
                for i, q in enumerate(sub_queries)
            }
            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as exc:
                    # A single sub-query failing must not sink the whole search.
                    logger.warning(
                        "research_agent.search.subquery_failed",
                        sub_query=sub_queries[idx][:80],
                        error=str(exc),
                    )
                    results[idx] = []

        return results

    def _search_one(self, sub_query: str, chain: list) -> list[dict]:
        """
        Circuit breaker for ONE sub-query: try each tool in order, return the
        first non-empty result set. A SearchToolError falls through to the next
        tool; if every tool fails or is empty, return [].
        """
        for tool in chain:
            try:
                found = tool.search(sub_query)
            except SearchToolError as exc:
                logger.info(
                    "research_agent.search.tool_fellback",
                    tool=type(tool).__name__,
                    sub_query=sub_query[:80],
                    reason=str(exc),
                )
                continue
            if found:
                return found
        return []

    def _deduplicate(
        self,
        per_query_results: list[list[dict]],
        state: ResearchState,
    ) -> list[dict]:
        """
        Flatten all sub-query results into one list, keeping each URL only once.
        URLs already collected on a previous retry (state['sources_used']) are
        skipped so retries add genuinely NEW sources, not duplicates.
        """
        seen: set[str] = set(state.get("sources_used") or [])
        deduped: list[dict] = []

        for results in per_query_results:
            for item in results:
                url = item.get("url", "")
                if not url or url in seen:
                    continue
                seen.add(url)
                deduped.append(item)

        return deduped
