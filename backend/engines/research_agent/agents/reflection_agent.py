"""
engines/research_agent/agents/reflection_agent.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ReflectionAgent — the self-critic. The LAST node, and the second (and final)
agentic decision point in the whole graph.

It reads the finished report and scores its OWN quality 0.0–1.0. The router
(route_after_reflection) then decides:
  - score >= 0.7              → END (good enough, ship it)
  - score <  0.7 + budget left → loop ALL the way back to the planner (re-plan)
  - score <  0.7 + budget spent → END anyway (best-effort)

This is the "Reflexion" pattern — an agent grading and improving its own work.

THE retry_count CONTRACT (mirrors VerificationAgent):
  retry_count is the SHARED global "corrective-loop budget" for the whole
  pipeline (verification retries AND reflection re-plans draw from the same
  pool). Reflection increments it whenever it produces a sub-threshold score,
  so the re-plan loop is guaranteed to terminate:
      low score #1 → retry_count +1 → router: within budget → RE-PLAN
      low score #2 → retry_count +1 → router: budget spent  → END
  Without this increment, a report that keeps scoring low would re-plan forever.

SPEED CHOICE: Cerebras. Scoring is a quick judgement; fast model, low cost.

Provider: Cerebras | max_tokens: 512 (MAX_TOKENS_REFLECTION).
"""

from __future__ import annotations

import json
import structlog
from pydantic import BaseModel, field_validator

from engines.research_agent.agents.base_agent import BaseAgent
from engines.research_agent.constants import (
    AgentName,
    MAX_TOKENS_REFLECTION,
    JSON_RESPONSE_FORMAT,
)
from engines.research_agent.graph.state import ResearchState

logger = structlog.get_logger(__name__)

# Must match the threshold the router uses in route_after_reflection.
# Below this, Reflection counts the report as needing improvement.
REFLECTION_PASS_THRESHOLD = 0.7


class ReflectionOutput(BaseModel):
    """Validated shape of the self-critique."""

    score: float
    notes: str = ""

    @field_validator("score")
    @classmethod
    def _clamp(cls, v: float) -> float:
        # Keep the score in [0.0, 1.0] no matter what the LLM emits.
        return max(0.0, min(1.0, v))


_SYSTEM_PROMPT = (
    "You are a demanding quality reviewer for an Indian UPSC exam preparation "
    "platform. You score research reports for completeness, factual grounding, "
    "clarity, and exam usefulness. Be honest and calibrated: 0.9+ is excellent, "
    "0.7-0.9 is solid, below 0.7 means it genuinely needs another research pass. "
    "Always respond with ONLY a valid JSON object — no markdown, no prose."
)


class ReflectionAgent(BaseAgent):
    agent_name = AgentName.REFLECTION
    model_provider = "cerebras"
    model_name = (
        "gpt-oss-120b"  # Cerebras free production model (Llama retired from public)
    )
    max_tokens = MAX_TOKENS_REFLECTION

    def execute(self, state: ResearchState) -> tuple[dict, int]:
        query = (state.get("query") or "").strip()
        report = (state.get("final_report") or "").strip()
        current_retry = state.get("retry_count", 0)

        # ── Nothing to evaluate → end cleanly, no pointless re-plan ───────────
        # Score exactly at threshold so the router's `>= 0.7` check ends the run.
        if not report:
            logger.info(
                "research_agent.reflection.nothing_to_evaluate",
                session_id=state.get("session_id"),
            )
            return (
                {
                    "reflection_score": REFLECTION_PASS_THRESHOLD,
                    "reflection_notes": "No report to evaluate; ending best-effort.",
                },
                0,
            )

        # ── LLM self-critique (Cerebras) ──────────────────────────────────────
        user_prompt = self._build_prompt(query, report)
        text, tokens = self._call_llm(
            prompt=user_prompt,
            system=_SYSTEM_PROMPT,
            max_tokens=self.max_tokens,
            response_format=JSON_RESPONSE_FORMAT,
        )

        score, notes = self._parse(text)

        partial: dict = {
            "reflection_score": score,
            "reflection_notes": notes,
        }

        # ── Sub-threshold → spend a corrective-loop unit (bounds the re-plan) ─
        if score < REFLECTION_PASS_THRESHOLD:
            partial["retry_count"] = current_retry + 1
            logger.warning(
                "research_agent.reflection.low_score",
                session_id=state.get("session_id"),
                score=score,
                retry_count=partial["retry_count"],
            )
        else:
            logger.info(
                "research_agent.reflection.passed",
                session_id=state.get("session_id"),
                score=score,
            )

        return partial, tokens

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────────────────────────────────
    def _build_prompt(self, query: str, report: str) -> str:
        return (
            f'Research question: "{query}"\n\n'
            f"REPORT TO SCORE:\n{report}\n\n"
            "Produce a JSON object with exactly these keys:\n"
            '  "score": a number 0.0-1.0 rating the report\'s overall quality.\n'
            '  "notes": one sentence on the main strength or weakness.\n\n'
            "Respond with ONLY the JSON object."
        )

    def _parse(self, text: str) -> tuple[float, str]:
        """
        Parse the self-critique. Lenient: if the critic's own output can't be
        parsed, DEFAULT TO PASS (score = threshold) so we END rather than burn a
        re-plan loop on a formatting glitch.
        """
        try:
            raw = self._extract_json(text)
            data = json.loads(raw)
            parsed = ReflectionOutput.model_validate(data)
            return parsed.score, parsed.notes
        except Exception as exc:
            logger.warning(
                "research_agent.reflection.parse_fallback",
                error=str(exc),
                raw_preview=text[:200],
            )
            return (
                REFLECTION_PASS_THRESHOLD,
                "Critic output unparseable; defaulting to pass.",
            )

    @staticmethod
    def _extract_json(text: str) -> str:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("no JSON object found in response")
        return text[start : end + 1]
