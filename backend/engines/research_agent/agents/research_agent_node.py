"""
engines/research_agent/agents/research_agent_node.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ResearchAgentNode — the synthesizer. The FIRST heavy LLM call.

The Search agent handed over a clean, credibility-sorted stack of sources.
This agent READS that stack and WRITES coherent findings:
  - synthesized_content : a flowing prose synthesis of the evidence
  - key_findings        : bullet-point facts (each later fact-checked by Verify)

Two production guards baked in:
  • CONTEXT BUDGET (Risk #8): we never dump unlimited source text into the LLM.
    Sources are already credibility-sorted, so we include the BEST ones up to a
    character budget and stop — protecting both cost and the context window.
  • LENIENT PARSE (Risk #46): if the LLM returns malformed JSON, we don't crash —
    we use the raw text as the synthesis and continue best-effort.

Provider: Groq llama-3.3-70b | max_tokens: 1200 (MAX_TOKENS_RESEARCH).

NOTE: File named research_agent_node.py to avoid a name clash with the engine
package name `research_agent`.
"""

from __future__ import annotations

import json
import structlog
from pydantic import BaseModel, field_validator

from engines.research_agent.agents.base_agent import BaseAgent
from engines.research_agent.constants import (
    AgentName,
    MAX_TOKENS_RESEARCH,
    JSON_RESPONSE_FORMAT,
)
from engines.research_agent.graph.state import ResearchState

logger = structlog.get_logger(__name__)

# Context budget for source text fed to the LLM (Risk #8).
# Each source is now ≤800 chars; this caps the TOTAL across all sources.
# ~12000 chars ≈ 3000 tokens of evidence — richer grounding, still bounded.
MAX_CONTEXT_CHARS = 12000
MAX_SOURCES_IN_CONTEXT = 15


class ResearchOutput(BaseModel):
    """Validated shape of the Research agent's LLM response."""

    synthesized_content: str
    key_findings: list[str]

    @field_validator("key_findings")
    @classmethod
    def _clean_findings(cls, v: list[str]) -> list[str]:
        return [f.strip() for f in v if f and f.strip()]


_SYSTEM_PROMPT = (
    "You are a meticulous research analyst for an Indian UPSC exam preparation "
    "platform. You are given a research question and a numbered list of sources. "
    "Synthesize ONLY what the sources support — never invent facts. Cite sources "
    "by their number like [1], [3] inside the synthesis. "
    "Always respond with ONLY a valid JSON object — no markdown, no prose."
)


class ResearchAgentNode(BaseAgent):
    agent_name = AgentName.RESEARCH
    model_provider = "groq"
    model_name = "llama-3.3-70b-versatile"
    max_tokens = MAX_TOKENS_RESEARCH

    def execute(self, state: ResearchState) -> tuple[dict, int]:
        query = (state.get("query") or "").strip()
        sources = state.get("raw_search_results") or []

        # ── No sources → best-effort empty synthesis (don't call the LLM) ─────
        if not sources:
            logger.warning(
                "research_agent.research.no_sources",
                session_id=state.get("session_id"),
            )
            return (
                {
                    "synthesized_content": (
                        "No sources were found for this query. "
                        "A reliable answer could not be synthesized."
                    ),
                    "key_findings": [],
                },
                0,
            )

        # ── Build a bounded context from the best sources (Risk #8) ───────────
        context, used_count = self._build_context(sources)

        user_prompt = self._build_prompt(query, context, used_count)
        text, tokens = self._call_llm(
            prompt=user_prompt,
            system=_SYSTEM_PROMPT,
            max_tokens=self.max_tokens,
            response_format=JSON_RESPONSE_FORMAT,
        )

        synthesized, findings = self._parse(text)

        logger.info(
            "research_agent.research.completed",
            session_id=state.get("session_id"),
            sources_available=len(sources),
            sources_used=used_count,
            findings=len(findings),
        )

        partial = {
            "synthesized_content": synthesized,
            "key_findings": findings,
        }
        return partial, tokens

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────────────────────────────────
    def _build_context(self, sources: list[dict]) -> tuple[str, int]:
        """
        Turn the credibility-sorted sources into a numbered context block,
        including the best ones until the character budget is hit.
        Returns (context_text, sources_used_count).
        """
        lines: list[str] = []
        total_chars = 0
        used = 0

        for i, src in enumerate(sources[:MAX_SOURCES_IN_CONTEXT], start=1):
            title = src.get("title", "") or "Untitled"
            url = src.get("url", "")
            content = src.get("content", "") or ""

            block = f"[{i}] {title} ({url})\n{content}\n"
            if total_chars + len(block) > MAX_CONTEXT_CHARS and used > 0:
                # Budget reached — stop adding more sources.
                break

            lines.append(block)
            total_chars += len(block)
            used += 1

        return "\n".join(lines), used

    def _build_prompt(self, query: str, context: str, source_count: int) -> str:
        return (
            f'Research question: "{query}"\n\n'
            f"Sources (numbered [1] to [{source_count}]):\n{context}\n"
            "CITATION RULES (strict):\n"
            f"  - You may cite ONLY the numbers [1] through [{source_count}].\n"
            f"  - NEVER cite a number greater than [{source_count}] or invent a citation.\n"
            "  - If a fact is not supported by any source, state it plainly "
            "WITHOUT a citation rather than fabricating one.\n\n"
            "Produce a JSON object with exactly these keys:\n"
            '  "synthesized_content": a coherent 250-400 word synthesis that '
            "answers the question using ONLY the sources above, citing them as "
            "[n] per the rules.\n"
            '  "key_findings": an array of 4-7 concise factual bullet points, '
            "each grounded in a cited source.\n\n"
            "Respond with ONLY the JSON object."
        )

    def _parse(self, text: str) -> tuple[str, list[str]]:
        """
        Parse the LLM response into (synthesized_content, key_findings).
        Lenient: on any failure, use the raw text as the synthesis so the
        pipeline continues (Risk #46).
        """
        try:
            raw = self._extract_json(text)
            data = json.loads(raw)
            parsed = ResearchOutput.model_validate(data)
            return parsed.synthesized_content, parsed.key_findings
        except Exception as exc:
            logger.warning(
                "research_agent.research.parse_fallback",
                error=str(exc),
                raw_preview=text[:200],
            )
            return text.strip(), []

    @staticmethod
    def _extract_json(text: str) -> str:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("no JSON object found in response")
        return text[start : end + 1]
