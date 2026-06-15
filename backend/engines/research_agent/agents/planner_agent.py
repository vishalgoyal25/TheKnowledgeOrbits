"""
engines/research_agent/agents/planner_agent.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PlannerAgent — the first THINKING agent.

Given the raw question, it decides the research strategy:
  1. Classify the domain (polity / economy / science / ...) — cheap, no LLM.
  2. Ask the LLM to break the question into ≤3 focused search sub-queries
     plus a short research plan.

Why sub-queries?
  A single question like "Impact of GST on Indian federalism" searches poorly
  as one string. Split into 3 angles — "GST structure", "GST and state
  revenue", "GST Council federalism debate" — and the Search agent gets far
  richer, more targeted results.

Output is parsed through a LENIENT Pydantic model (Risk #46): if the LLM
returns malformed JSON, we DON'T crash — we fall back to searching the raw
query directly, log a warning, and let the pipeline continue best-effort.

Provider: Groq | max_tokens: 1024 (MAX_TOKENS_PLANNER).
"""

from __future__ import annotations

import json
import structlog
from pydantic import BaseModel, field_validator

from engines.research_agent.agents.base_agent import BaseAgent
from engines.research_agent.constants import (
    AgentName,
    MAX_SEARCH_QUERIES,
    MAX_TOKENS_PLANNER,
    JSON_RESPONSE_FORMAT,
)
from engines.research_agent.graph.state import ResearchState
from engines.research_agent.tools.registry import tool_registry

logger = structlog.get_logger(__name__)


class PlannerOutput(BaseModel):
    """Validated shape of the Planner's LLM response."""

    research_plan: str
    sub_queries: list[str]

    @field_validator("sub_queries")
    @classmethod
    def _clean_sub_queries(cls, v: list[str]) -> list[str]:
        # Drop blanks, strip whitespace, enforce the hard cap of 3.
        cleaned = [q.strip() for q in v if q and q.strip()]
        if not cleaned:
            raise ValueError("sub_queries is empty after cleaning")
        return cleaned[:MAX_SEARCH_QUERIES]


_SYSTEM_PROMPT = (
    "You are an expert research planner for an Indian UPSC exam preparation "
    "platform. Given a research question, you produce a concise research plan "
    "and break it into focused web-search sub-queries. "
    "Always respond with ONLY a valid JSON object — no markdown, no prose."
)


class PlannerAgent(BaseAgent):
    agent_name = AgentName.PLANNER
    model_provider = "groq"
    model_name = "llama-3.3-70b-versatile"
    max_tokens = MAX_TOKENS_PLANNER

    def execute(self, state: ResearchState) -> tuple[dict, int]:
        query = (state.get("query") or "").strip()

        # ── 1. Domain classification (cheap, deterministic, no LLM) ───────────
        domain = tool_registry.get("domain").classify(query)

        # ── 2. Ask the LLM for a plan + sub-queries ───────────────────────────
        user_prompt = self._build_prompt(query, domain)
        text, tokens = self._call_llm(
            prompt=user_prompt,
            system=_SYSTEM_PROMPT,
            max_tokens=self.max_tokens,
            response_format=JSON_RESPONSE_FORMAT,
        )

        # ── 3. Parse (lenient — never crash on bad LLM output) ────────────────
        plan, sub_queries = self._parse(text, query)

        logger.info(
            "research_agent.planner.completed",
            session_id=state.get("session_id"),
            domain=domain,
            sub_query_count=len(sub_queries),
        )

        partial = {
            "domain": domain,
            "research_plan": plan,
            "sub_queries": sub_queries,
        }
        return partial, tokens

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────────────────────────────────
    def _build_prompt(self, query: str, domain: str) -> str:
        return (
            f'Research question: "{query}"\n'
            f"Knowledge domain: {domain}\n\n"
            "Produce a JSON object with exactly these keys:\n"
            '  "research_plan": a 2-3 sentence plan describing what to '
            "investigate and in what order.\n"
            f'  "sub_queries": an array of at most {MAX_SEARCH_QUERIES} focused, '
            "self-contained web-search queries that together fully cover the "
            "question.\n\n"
            "Respond with ONLY the JSON object."
        )

    def _parse(self, text: str, query: str) -> tuple[str, list[str]]:
        """
        Parse the LLM response into (research_plan, sub_queries).
        Lenient: any failure falls back to searching the raw query directly.
        """
        try:
            raw = self._extract_json(text)
            data = json.loads(raw)
            parsed = PlannerOutput.model_validate(data)
            return parsed.research_plan, parsed.sub_queries
        except Exception as exc:
            logger.warning(
                "research_agent.planner.parse_fallback",
                error=str(exc),
                raw_preview=text[:200],
            )
            # Best-effort fallback (Risk #46): just search the original query.
            return (
                "Fallback plan: planner output could not be parsed; "
                "searching the original query directly.",
                [query],
            )

    @staticmethod
    def _extract_json(text: str) -> str:
        """
        Pull the JSON object out of the response, tolerating markdown fences
        or stray prose around it (LLMs love to add ```json wrappers).
        """
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("no JSON object found in response")
        return text[start : end + 1]
