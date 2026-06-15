"""
engines/research_agent/agents/verification_agent.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VerificationAgent — the fact-checker. The quality gate.

It reads the Research agent's synthesis + key findings and judges ONE thing:
  "Is this well-grounded in the sources, or did it drift / hallucinate?"

It returns a verdict (verification_passed) that the ROUTER uses to decide:
  - passed       → proceed to summary
  - failed + budget left → loop back to search and try again (1 retry max)
  - failed + budget spent → proceed anyway (best-effort report)

THE retry_count CONTRACT (read carefully — this is where loops are born or
prevented):
  This agent OWNS the retry_count increment. It bumps retry_count by 1 on every
  FAILED verdict. The router then allows a retry while `retry_count <=
  MAX_VERIFICATION_RETRIES`. So:
      fail #1 → retry_count=1 → router: 1 <= 1 → RETRY
      fail #2 → retry_count=2 → router: 2 <= 1 → GIVE UP (best-effort)
  Exactly one retry. No infinite loop.

SPEED CHOICE (Opt #1): runs on CEREBRAS, not Groq. Verification is a simple
yes/no judgement — Cerebras is ~10x faster, saving ~12s per pipeline run.
The multi-provider pool still fails over to Groq/Gemini if Cerebras is down.

Provider: Cerebras | max_tokens: 1024 (MAX_TOKENS_VERIFICATION).
"""

from __future__ import annotations

import json
import structlog
from pydantic import BaseModel

from engines.research_agent.agents.base_agent import BaseAgent
from engines.research_agent.constants import (
    AgentName,
    MAX_TOKENS_VERIFICATION,
    JSON_RESPONSE_FORMAT,
)
from engines.research_agent.graph.state import ResearchState

logger = structlog.get_logger(__name__)

# How many sources to show the judge as the ground-truth reference.
MAX_SOURCES_FOR_JUDGE = 10


class VerificationOutput(BaseModel):
    """Validated shape of the verifier's verdict."""

    passed: bool
    notes: str = ""


_SYSTEM_PROMPT = (
    "You are a strict fact-checking editor for an Indian UPSC exam preparation "
    "platform. You are given a synthesized answer, its key findings, and the "
    "source list it was built from. Judge whether the answer is well-grounded "
    "in those sources and free of unsupported claims. Be strict but fair: minor "
    "wording is fine; invented facts or claims absent from the sources fail. "
    "Always respond with ONLY a valid JSON object — no markdown, no prose."
)


class VerificationAgent(BaseAgent):
    agent_name = AgentName.VERIFICATION
    # Opt #1 — Cerebras for speed. Pool fails over to groq/gemini if it's down.
    model_provider = "cerebras"
    model_name = (
        "gpt-oss-120b"  # Cerebras free production model (Llama retired from public)
    )
    max_tokens = MAX_TOKENS_VERIFICATION

    def execute(self, state: ResearchState) -> tuple[dict, int]:
        synthesized = (state.get("synthesized_content") or "").strip()
        findings = state.get("key_findings") or []
        sources = state.get("raw_search_results") or []
        current_retry = state.get("retry_count", 0)

        # ── Nothing meaningful to verify → pass through (retry won't help) ────
        # If Research produced no grounded content (e.g. no sources existed),
        # looping back to search is pointless. Approve best-effort and move on.
        if not synthesized or not sources:
            logger.info(
                "research_agent.verification.nothing_to_verify",
                session_id=state.get("session_id"),
            )
            return (
                {
                    "verification_passed": True,
                    "verification_notes": "No grounded content to verify; proceeding best-effort.",
                },
                0,
            )

        # ── LLM judge (Cerebras) ──────────────────────────────────────────────
        user_prompt = self._build_prompt(synthesized, findings, sources)
        text, tokens = self._call_llm(
            prompt=user_prompt,
            system=_SYSTEM_PROMPT,
            max_tokens=self.max_tokens,
            response_format=JSON_RESPONSE_FORMAT,
        )

        passed, notes = self._parse(text)

        if passed:
            logger.info(
                "research_agent.verification.passed",
                session_id=state.get("session_id"),
            )
            return (
                {"verification_passed": True, "verification_notes": notes},
                tokens,
            )

        # ── Failed → increment retry_count (the loop budget counter) ──────────
        new_retry = current_retry + 1
        logger.warning(
            "research_agent.verification.failed",
            session_id=state.get("session_id"),
            retry_count=new_retry,
            notes=notes,
        )
        return (
            {
                "verification_passed": False,
                "verification_notes": notes,
                "retry_count": new_retry,
            },
            tokens,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────────────────────────────────
    def _build_prompt(
        self,
        synthesized: str,
        findings: list[str],
        sources: list[dict],
    ) -> str:
        source_lines = []
        for i, src in enumerate(sources[:MAX_SOURCES_FOR_JUDGE], start=1):
            title = src.get("title", "") or "Untitled"
            content = src.get("content", "") or ""
            source_lines.append(f"[{i}] {title}: {content}")
        source_block = "\n".join(source_lines)

        findings_block = "\n".join(f"- {f}" for f in findings) or "(none)"

        return (
            "ANSWER TO CHECK:\n"
            f"{synthesized}\n\n"
            "KEY FINDINGS:\n"
            f"{findings_block}\n\n"
            "SOURCES (ground truth):\n"
            f"{source_block}\n\n"
            "Produce a JSON object with exactly these keys:\n"
            '  "passed": true if the answer is well-grounded in the sources, '
            "false if it contains unsupported or invented claims.\n"
            '  "notes": one sentence explaining your verdict.\n\n'
            "Respond with ONLY the JSON object."
        )

    def _parse(self, text: str) -> tuple[bool, str]:
        """
        Parse the verifier's verdict. Lenient: if the judge's own output can't
        be parsed, DEFAULT TO PASSED — better to proceed than to burn a retry
        on a judge formatting glitch (the retry budget is precious).
        """
        try:
            raw = self._extract_json(text)
            data = json.loads(raw)
            parsed = VerificationOutput.model_validate(data)
            return parsed.passed, parsed.notes
        except Exception as exc:
            logger.warning(
                "research_agent.verification.parse_fallback",
                error=str(exc),
                raw_preview=text[:200],
            )
            return True, "Verifier output unparseable; defaulting to pass."

    @staticmethod
    def _extract_json(text: str) -> str:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("no JSON object found in response")
        return text[start : end + 1]
