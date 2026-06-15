"""
engines/research_agent/agents/summary_generator.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SummaryGeneratorAgent — writes the 300-word executive summary FIRST (Opt #2).

Why a separate summary agent BEFORE the full report?
  The full report takes ~15s to generate. If the user waits for the whole thing,
  they stare at a blank screen. Instead, we generate a tight ~300-word summary
  first and stream it at ~75s — the user starts READING immediately while the
  full report generates in the background. Perceived wait drops dramatically.

This is a pure prose task — NO JSON, NO structured parsing. We take the LLM's
text output directly as the executive summary. Simpler and faster.

SPEED CHOICE: runs on CEREBRAS gpt-oss-120b — the fastest provider (~3000 tok/s),
and the summary is on the critical path to "user sees something." Pool fails over
to Groq if Cerebras is down.

Provider: Cerebras (gpt-oss-120b) | max_tokens: 600 (MAX_TOKENS_SUMMARY ≈ 300 words).
"""

from __future__ import annotations

import structlog

from engines.research_agent.agents.base_agent import BaseAgent
from engines.research_agent.constants import AgentName, MAX_TOKENS_SUMMARY
from engines.research_agent.graph.state import ResearchState

logger = structlog.get_logger(__name__)


_SYSTEM_PROMPT = (
    "You are an expert exam-prep writer for an Indian UPSC platform. You write "
    "crisp, factual executive summaries. Given a synthesized research answer and "
    "its key findings, write a single self-contained executive summary of about "
    "300 words. No headings, no bullet points, no preamble like 'Here is' — just "
    "the summary prose itself, ready to show the reader."
)


class SummaryGeneratorAgent(BaseAgent):
    agent_name = AgentName.SUMMARY_GENERATOR
    # Fast provider — this is the first thing the user reads.
    model_provider = "cerebras"
    model_name = (
        "gpt-oss-120b"  # Cerebras free production model (Llama retired from public)
    )
    max_tokens = MAX_TOKENS_SUMMARY

    def execute(self, state: ResearchState) -> tuple[dict, int]:
        query = (state.get("query") or "").strip()
        synthesized = (state.get("synthesized_content") or "").strip()
        findings = state.get("key_findings") or []

        # ── No content to summarize → minimal honest fallback (no LLM) ────────
        if not synthesized:
            logger.warning(
                "research_agent.summary.no_content",
                session_id=state.get("session_id"),
            )
            return (
                {
                    "executive_summary": (
                        "A reliable summary could not be generated because no "
                        "grounded research content was available for this query."
                    ),
                },
                0,
            )

        # ── Generate the summary (plain prose, no JSON) ───────────────────────
        user_prompt = self._build_prompt(query, synthesized, findings)
        text, tokens = self._call_llm(
            prompt=user_prompt,
            system=_SYSTEM_PROMPT,
            max_tokens=self.max_tokens,
        )

        summary = text.strip()

        logger.info(
            "research_agent.summary.completed",
            session_id=state.get("session_id"),
            summary_words=len(summary.split()),
        )

        return {"executive_summary": summary}, tokens

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────────────────────────────────
    def _build_prompt(self, query: str, synthesized: str, findings: list[str]) -> str:
        findings_block = "\n".join(f"- {f}" for f in findings) or "(none)"
        return (
            f'Research question: "{query}"\n\n'
            f"Synthesized answer:\n{synthesized}\n\n"
            f"Key findings:\n{findings_block}\n\n"
            "Write the ~300-word executive summary now."
        )
