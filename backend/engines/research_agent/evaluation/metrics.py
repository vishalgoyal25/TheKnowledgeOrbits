"""
engines/research_agent/evaluation/metrics.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Evaluation metric definitions + the LLM-as-judge prompt.

We use the DeepEval METHODOLOGY (LLM-as-judge scoring of faithfulness, relevance,
hallucination, completeness) but run the judge through OUR Groq/Cerebras pool —
reliable JSON (response_format), provider failover, and rate-limit accounting we
already built — instead of DeepEval's OpenAI-default runner. Results stay LOCAL
(saved to ra_evaluation), per the locked decision (no external eval dashboard).

Score conventions (must match EvaluationResult.compute_and_save_composite):
  faithfulness  1.0 = every claim grounded in the sources        (higher better)
  relevance     1.0 = fully answers the question                 (higher better)
  hallucination 0.0 = no invented facts, 1.0 = many              (LOWER better)
  completeness  1.0 = covers all aspects of the question         (higher better)

The composite weighting lives in the MODEL (authoritative):
  faithfulness .35 · relevance .30 · (1-hallucination) .20 · completeness .15
"""

from __future__ import annotations

METRIC_NAMES = ["faithfulness", "relevance", "hallucination", "completeness"]

# Soft thresholds — below these we log a quality warning (not blocking).
METRIC_THRESHOLDS = {
    "faithfulness": 0.65,
    "relevance": 0.60,
    "hallucination": 0.30,  # ABOVE this = too much hallucination
    "completeness": 0.55,
}

JUDGE_SYSTEM_PROMPT = (
    "You are a strict, calibrated evaluation judge for an Indian UPSC research "
    "platform. You score a generated REPORT against the SOURCES it was built "
    "from, on four metrics, each 0.0-1.0. Be objective and consistent. "
    "Always respond with ONLY a valid JSON object — no markdown, no prose."
)


def build_judge_prompt(query: str, report: str, sources: list[dict]) -> str:
    """Build the single combined judge prompt (one LLM call scores all 4 metrics)."""
    source_lines = []
    for i, s in enumerate(sources or [], start=1):
        title = (s.get("title") or "Untitled") if isinstance(s, dict) else str(s)
        url = s.get("url", "") if isinstance(s, dict) else ""
        source_lines.append(f"[{i}] {title} {url}".strip())
    source_block = "\n".join(source_lines) or "(no sources)"

    return (
        f'QUESTION:\n"{query}"\n\n'
        f"SOURCES:\n{source_block}\n\n"
        f"REPORT TO EVALUATE:\n{report[:6000]}\n\n"
        "Score the report 0.0-1.0 on each metric:\n"
        "  faithfulness  — are the report's claims grounded in the sources? (higher = better)\n"
        "  relevance     — does it actually answer the question? (higher = better)\n"
        "  hallucination — does it invent facts not in the sources? (0.0 = none, 1.0 = many; LOWER = better)\n"
        "  completeness  — does it cover the key aspects of the question? (higher = better)\n\n"
        "Respond with ONLY this JSON shape:\n"
        '{"faithfulness": {"score": 0.0, "reason": "..."}, '
        '"relevance": {"score": 0.0, "reason": "..."}, '
        '"hallucination": {"score": 0.0, "reason": "..."}, '
        '"completeness": {"score": 0.0, "reason": "..."}}'
    )
