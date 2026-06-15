"""
engines/research_agent/models/research_report.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ResearchReport — stores the final output after ReportGenerator completes.
One report per session (OneToOne → ra_session).

DB table: ra_report
"""

from __future__ import annotations

import uuid
import structlog
import sentry_sdk
from django.db import models

logger = structlog.get_logger(__name__)


class ResearchReport(models.Model):
    """
    Created by the Orchestrator after ReportGenerator node finishes.
    Contains both the executive summary (shown first at ~75s) and
    the full Markdown report (streamed token-by-token after summary).

    confidence_score is initially None — updated later by DeepEval
    evaluation task AFTER workflow_completed SSE fires (never blocks user).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # OneToOne — every session has exactly one report (or none if failed).
    session = models.OneToOneField(
        "research_agent.ResearchSession",
        on_delete=models.CASCADE,
        related_name="report",
    )

    # 300-word executive summary generated FIRST by SummaryGeneratorAgent (Opt #2).
    # User reads this while full report is still streaming.
    executive_summary = models.TextField(
        help_text="300-word summary streamed to user first at ~75s.",
    )

    # Full structured Markdown report from ReportGenerator.
    full_report = models.TextField(
        help_text="Complete Markdown research report.",
    )

    # List of sources used: [{url, title, credibility_score}]
    # JSONField — stored as JSONB in PostgreSQL (fast queries, GIN indexable).
    sources = models.JSONField(
        default=list,
        help_text="List of {url, title, credibility_score} dicts.",
    )

    # Derived from DeepEval scores — shown to user as 'Research Confidence %'.
    # Null until evaluation_task completes (may be a few seconds after report).
    confidence_score = models.FloatField(
        null=True,
        blank=True,
        help_text="0.0–1.0 composite score from DeepEval. Null until eval completes.",
    )

    word_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "research_agent"
        db_table = "ra_report"

    def __str__(self) -> str:
        return f"ResearchReport({self.session_id} | words={self.word_count} | confidence={self.confidence_score})"

    def update_confidence(self, score: float) -> None:
        """
        Called by evaluation_task AFTER workflow_completed SSE fires.
        Updates confidence_score without touching any other field.
        """
        try:
            self.confidence_score = score
            self.save(update_fields=["confidence_score"])
            logger.info(
                "research_agent.report.confidence_updated",
                session_id=str(self.session_id),
                score=score,
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise
