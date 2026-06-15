"""
engines/research_agent/agents/report_generator.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ReportGeneratorAgent — writes the FULL structured Markdown report.

This is the headline output. Two things make it special:

  1. IT STREAMS (Opt #2 / Risk #9). Instead of generating the whole report and
     then dumping it, it streams token-by-token via the pool's call_stream().
     Each token is pushed to the user's browser through SSE (Phase 5 hook), so
     the report appears to "type itself out" live — the user reads as it writes.

  2. IT'S GROUNDED. It builds ONLY on the verified synthesis, key findings, and
     the executive summary the earlier agents produced — citing sources as [n].
     It does not re-research; it composes what's already been verified.

Why stream the FULL report when we already streamed a summary?
  The summary (~75s) gives the user the gist fast. The full report streams right
  after, so by the time they finish the summary, the detailed report is already
  filling in below — zero perceived dead time.

Provider: Groq llama-3.3-70b (quality matters here) | max_tokens: 1500.
"""

from __future__ import annotations

import structlog

from engines.research_agent.agents.base_agent import BaseAgent
from engines.research_agent.constants import AgentName, MAX_TOKENS_REPORT_GENERATOR
from engines.research_agent.graph.state import ResearchState

logger = structlog.get_logger(__name__)


# SSE emit batching: flush buffered tokens to Redis once the buffer reaches this
# many characters (instead of one network publish per token). A remote Redis
# (Upstash, ~250ms RTT) makes per-token publishing dominate runtime — batching
# cuts ~600 publishes down to a few dozen while still streaming smoothly.
_STREAM_FLUSH_CHARS = 80


_SYSTEM_PROMPT = (
    "You are an expert research-report writer for an Indian UPSC exam "
    "preparation platform. You write thorough, well-structured, exam-ready "
    "Markdown reports grounded STRICTLY in the material provided. Use clear "
    "section headings (##), short paragraphs, and bullet points where helpful. "
    "Cite sources inline as [n]. NEVER invent facts, names, numbers, dates, or "
    "events that are not in the provided material — if the material doesn't "
    "cover something, omit it rather than fabricating. Output ONLY the Markdown "
    "report — no preamble, no 'Here is' framing."
)


class ReportGeneratorAgent(BaseAgent):
    agent_name = AgentName.REPORT_GENERATOR
    model_provider = "groq"
    model_name = "llama-3.3-70b-versatile"
    max_tokens = MAX_TOKENS_REPORT_GENERATOR

    def execute(self, state: ResearchState) -> tuple[dict, int]:
        query = (state.get("query") or "").strip()
        synthesized = (state.get("synthesized_content") or "").strip()
        findings = state.get("key_findings") or []
        summary = (state.get("executive_summary") or "").strip()
        sources = state.get("raw_search_results") or []

        # ── No grounded content → fall back to the summary as the report ──────
        if not synthesized:
            logger.warning(
                "research_agent.report.no_content",
                session_id=state.get("session_id"),
            )
            fallback = summary or (
                "A full report could not be generated because no grounded "
                "research content was available for this query."
            )
            return (
                {"final_report": fallback, "report_word_count": len(fallback.split())},
                0,
            )

        # ── Stream the full report token-by-token ─────────────────────────────
        user_prompt = self._build_prompt(query, summary, synthesized, findings, sources)

        chunks: list[str] = []
        buffer: list[str] = []
        buffered_chars = 0
        for delta in self._stream_llm(user_prompt, _SYSTEM_PROMPT, self.max_tokens):
            chunks.append(delta)  # full report always assembled
            buffer.append(delta)
            buffered_chars += len(delta)
            # Flush the SSE buffer in one publish once it's big enough.
            if buffered_chars >= _STREAM_FLUSH_CHARS:
                self._emit_token(state, "".join(buffer))
                buffer.clear()
                buffered_chars = 0
        # Flush whatever's left so the browser gets the tail of the report.
        if buffer:
            self._emit_token(state, "".join(buffer))

        report = "".join(chunks).strip()
        word_count = len(report.split())

        # Streaming responses don't return a usage block, so we estimate tokens
        # from output length (~4 chars/token) for telemetry.
        est_tokens = max(1, len(report) // 4)

        logger.info(
            "research_agent.report.completed",
            session_id=state.get("session_id"),
            word_count=word_count,
            est_tokens=est_tokens,
        )

        return (
            {"final_report": report, "report_word_count": word_count},
            est_tokens,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────────────────────────────────
    def _stream_llm(self, prompt: str, system: str, max_tokens: int):
        """
        Stream tokens from the LLM pool. Routes through the same global pool as
        every other call (Hard Rule), so it inherits provider failover.
        Lazily imported to keep module import cheap.
        """
        from engines.research_agent.llmops.groq_client import llm_client

        yield from llm_client.call_stream(
            prompt=prompt,
            system=system,
            provider=self.model_provider,
            model=self.model_name,
            max_tokens=max_tokens,
        )

    def _emit_token(self, state: ResearchState, token: str) -> None:
        """
        Push this token to the browser as an SSE `report_token` event so the
        report types itself out live. Defensive + lazily imported — a streaming
        SSE failure must never break report assembly (the full report is still
        accumulated and saved regardless).
        """
        try:
            from engines.research_agent.constants import SSEEvent
            from engines.research_agent.services.sse_service import sse_service

            sse_service.emit(
                state.get("session_id"), SSEEvent.REPORT_TOKEN, {"token": token}
            )
        except Exception:
            pass

    def _build_prompt(
        self,
        query: str,
        summary: str,
        synthesized: str,
        findings: list[str],
        sources: list[dict],
    ) -> str:
        findings_block = "\n".join(f"- {f}" for f in findings) or "(none)"

        source_lines = []
        for i, src in enumerate(sources, start=1):
            title = src.get("title", "") or "Untitled"
            url = src.get("url", "")
            source_lines.append(f"[{i}] {title} — {url}")
        source_block = "\n".join(source_lines) or "(none)"
        source_count = len(sources)

        return (
            f'Research question: "{query}"\n\n'
            f"Executive summary (for context):\n{summary}\n\n"
            f"Verified synthesis:\n{synthesized}\n\n"
            f"Key findings:\n{findings_block}\n\n"
            f"Sources, numbered [1] to [{source_count}]:\n{source_block}\n\n"
            "CITATION RULES (strict):\n"
            f"  - Cite ONLY the numbers [1] through [{source_count}]. "
            f"NEVER cite a number greater than [{source_count}] or invent one.\n"
            "  - Every factual claim should trace to a cited source; if it "
            "can't, omit it.\n\n"
            "Write the full structured Markdown report now (aim for ~800-1000 "
            "words). Include an introduction, several themed sections with ## "
            "headings, bullet points where useful, and a short conclusion. "
            "Cite sources inline as [n] per the rules."
        )
