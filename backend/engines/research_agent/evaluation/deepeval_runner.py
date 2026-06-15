"""
engines/research_agent/evaluation/deepeval_runner.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EvaluationRunner — scores a finished report AFTER the user already has it.

Runs the DeepEval-style 4-metric judge in ONE LLM call (cost-efficient — 1 call,
not 4 → easier on the shared free-tier quota) through our Groq/Cerebras pool
(failover + JSON mode). Never blocks the user — the orchestrator fires this in a
background task only after the session is completed (Risk #30).

Lazy singleton (Risk #17): there is no heavy local model to load — the judge
reuses the already-lazy `llm_client` pool singleton. So "load once, reuse" is
satisfied trivially.

Returns a scores dict the evaluation_task writes to ra_evaluation.
"""

from __future__ import annotations

import json

import structlog

from engines.research_agent.evaluation.metrics import (
    JUDGE_SYSTEM_PROMPT,
    METRIC_NAMES,
    METRIC_THRESHOLDS,
    build_judge_prompt,
)

logger = structlog.get_logger(__name__)


class EvaluationRunner:
    """Module-level singleton. Stateless; uses the shared LLM pool."""

    def evaluate(self, query: str, report: str, sources: list) -> dict:
        """
        Score the report. Returns:
          {faithfulness, relevance, hallucination, completeness,  # floats 0-1
           detail: {<metric>: {score, reason}}, tokens: int}
        On any failure, returns neutral 0.5 scores so the badge still renders.
        """
        prompt = build_judge_prompt(query, report, sources)
        try:
            from engines.research_agent.llmops.groq_client import llm_client

            text, tokens = llm_client.call(
                prompt=prompt,
                system=JUDGE_SYSTEM_PROMPT,
                provider="groq",
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            scores = self._parse(text)
            scores["tokens"] = tokens
            self._warn_low(scores)
            logger.info(
                "research_agent.eval.scored",
                faithfulness=scores["faithfulness"],
                relevance=scores["relevance"],
                hallucination=scores["hallucination"],
                completeness=scores["completeness"],
            )
            return scores
        except Exception as exc:
            logger.warning("research_agent.eval.failed", error=str(exc))
            return self._neutral()

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────────────────────────────────
    def _parse(self, text: str) -> dict:
        raw = self._extract_json(text)
        data = json.loads(raw)
        detail: dict = {}
        out: dict = {}
        for name in METRIC_NAMES:
            node = data.get(name, {})
            if isinstance(node, dict):
                score = float(node.get("score", 0.5))
                reason = str(node.get("reason", ""))[:300]
            else:  # tolerate a bare number
                score = float(node)
                reason = ""
            score = max(0.0, min(1.0, score))
            out[name] = score
            detail[name] = {"score": score, "reason": reason}
        out["detail"] = detail
        return out

    @staticmethod
    def _extract_json(text: str) -> str:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("no JSON object in judge response")
        return text[start : end + 1]

    @staticmethod
    def _warn_low(scores: dict) -> None:
        for name, threshold in METRIC_THRESHOLDS.items():
            val = scores.get(name, 0.0)
            # hallucination is inverted: ABOVE threshold is bad
            bad = val > threshold if name == "hallucination" else val < threshold
            if bad:
                logger.info(
                    "research_agent.eval.metric_below_bar", metric=name, score=val
                )

    @staticmethod
    def _neutral() -> dict:
        return {
            "faithfulness": 0.5,
            "relevance": 0.5,
            "hallucination": 0.5,
            "completeness": 0.5,
            "detail": {},
            "tokens": 0,
        }


# Module-level singleton.
evaluation_runner = EvaluationRunner()
