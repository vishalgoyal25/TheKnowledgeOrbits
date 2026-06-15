"""
engines/research_agent/models/evaluation_result.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EvaluationResult — stores raw DeepEval scores for one session.

Created by the DeepEval Celery task AFTER workflow_completed SSE fires.
Never blocks the user — runs as a background task.

DB table: ra_evaluation

4 DeepEval metrics stored as individual float columns:
  - hallucination_score   : 0.0 (no hallucination) → 1.0 (full hallucination)
  - faithfulness_score    : 0.0 → 1.0 (how grounded in sources)
  - relevance_score       : 0.0 → 1.0 (answer matches the question)
  - completeness_score    : 0.0 → 1.0 (all aspects of query covered)

composite_score = weighted average of all 4 → shown to user as "Research Confidence %"

Raw metric details (failure reasons, thresholds) stored in metrics_detail JSONField
for developer analysis in Langfuse / admin panel.
"""

from __future__ import annotations

import uuid
import structlog
import sentry_sdk
from django.db import models

logger = structlog.get_logger(__name__)


class EvaluationResult(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # OneToOne — one evaluation per session (DeepEval runs once, after completion).
    session = models.OneToOneField(
        "research_agent.ResearchSession",
        on_delete=models.CASCADE,
        related_name="evaluation",
    )

    # ── Raw DeepEval metric scores ────────────────────────────────────────────
    # Each is 0.0–1.0. Higher = better for all metrics except hallucination
    # (where lower = better — less hallucination).

    # G-Eval / Hallucination metric: lower is better.
    # 0.0 = no hallucination detected, 1.0 = heavily hallucinated output.
    hallucination_score = models.FloatField(
        null=True,
        blank=True,
        help_text="0.0 (clean) → 1.0 (hallucinated). Lower is better.",
    )

    # Faithfulness: is every claim grounded in the retrieved sources?
    faithfulness_score = models.FloatField(
        null=True,
        blank=True,
        help_text="0.0 → 1.0. Higher = more faithful to sources.",
    )

    # Answer Relevancy: does the report actually answer the query?
    relevance_score = models.FloatField(
        null=True,
        blank=True,
        help_text="0.0 → 1.0. Higher = more relevant to the original query.",
    )

    # Completeness: were all sub-questions / aspects of the query addressed?
    completeness_score = models.FloatField(
        null=True,
        blank=True,
        help_text="0.0 → 1.0. Higher = more complete coverage of the query.",
    )

    # ── Derived score ─────────────────────────────────────────────────────────
    # Weighted average — this is what gets written to ResearchReport.confidence_score.
    # Weights: faithfulness=0.35, relevance=0.30, hallucination=0.20, completeness=0.15
    # Faithfulness is highest — factual accuracy is paramount for UPSC exam prep.
    # Hallucination bumped to 0.20 — wrong facts = exam failure (critical safety check).
    # (hallucination is inverted: contribution = 0.20 * (1 - hallucination_score))
    composite_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Weighted composite 0.0–1.0. Written to ra_report.confidence_score.",
    )

    # ── Raw DeepEval output ───────────────────────────────────────────────────
    # Full metric output dicts: {score, reason, threshold, success}.
    # Stored for developer debugging — never exposed to end users.
    metrics_detail = models.JSONField(
        default=dict,
        help_text="Raw DeepEval metric output dicts for developer analysis.",
    )

    # How long DeepEval took to run (ms). Useful for performance monitoring.
    evaluation_duration_ms = models.IntegerField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "research_agent"
        db_table = "ra_evaluation"

    def __str__(self) -> str:
        return (
            f"EvaluationResult({self.session_id} | "
            f"composite={self.composite_score} | "
            f"hallucination={self.hallucination_score})"
        )

    def compute_and_save_composite(self) -> float:
        """
        Computes the weighted composite score from the 4 raw metric scores,
        saves it to this row, then writes it to the linked ResearchReport.

        Called by the DeepEval Celery task after all 4 metrics are populated.

        Weights:
          faithfulness   = 0.35  (highest — factual grounding, critical for UPSC)
          relevance      = 0.30  (answers the actual question)
          hallucination  = 0.20  (inverted — critical safety check)
          completeness   = 0.15  (coverage, nice-to-have)
          Total          = 1.00
        """
        try:
            faith = self.faithfulness_score or 0.0
            rel = self.relevance_score or 0.0
            comp = self.completeness_score or 0.0
            hall = self.hallucination_score or 0.0  # inverted below

            composite = faith * 0.35 + rel * 0.30 + (1.0 - hall) * 0.20 + comp * 0.15
            composite = round(min(max(composite, 0.0), 1.0), 4)

            self.composite_score = composite
            self.save(update_fields=["composite_score"])

            # Push composite score to the linked report
            if hasattr(self.session, "report"):
                self.session.report.update_confidence(composite)

            logger.info(
                "research_agent.evaluation.composite_computed",
                session_id=str(self.session_id),
                composite=composite,
                faithfulness=faith,
                relevance=rel,
                completeness=comp,
                hallucination=hall,
            )
            return composite

        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise
