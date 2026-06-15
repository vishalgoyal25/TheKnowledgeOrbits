"""
engines/research_agent/models/agent_execution_log.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AgentExecutionLog — one row per agent per session.

Records performance telemetry for each LangGraph node:
  - How long did it take? (duration_ms)
  - How many tokens did it consume? (tokens_used)
  - Which model/provider ran it? (groq / cerebras)
  - Did it succeed or fail?

DB table: ra_agent_log

This table is what makes the React Flow visualization possible —
the frontend reads these rows to show timing badges on each node.
Also visible in Langfuse trace timeline for LLMOps analysis.
"""

from __future__ import annotations

import uuid
import structlog
import sentry_sdk
from django.db import models

from engines.research_agent.constants import AgentName

logger = structlog.get_logger(__name__)


class AgentExecutionLog(models.Model):
    STATUS_STARTED = "started"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"  # e.g. agent skipped due to cancelled=True

    STATUS_CHOICES = [
        (STATUS_STARTED, "Started"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_SKIPPED, "Skipped"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    session = models.ForeignKey(
        "research_agent.ResearchSession",
        on_delete=models.CASCADE,
        related_name="agent_logs",
        db_index=True,
    )

    # Which agent produced this log row.
    # Values match AgentName constants (supervisor, planner, search, etc.)
    agent_name = models.CharField(
        max_length=64,
        choices=[
            (v, v)
            for v in [
                AgentName.SUPERVISOR,
                AgentName.PLANNER,
                AgentName.SEARCH,
                AgentName.RESEARCH,
                AgentName.VERIFICATION,
                AgentName.SUMMARY_GENERATOR,
                AgentName.REPORT_GENERATOR,
                AgentName.REFLECTION,
            ]
        ],
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_STARTED,
    )

    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)

    # Wall-clock time from node entry to node exit in milliseconds.
    # Null while status=started; filled on completion/failure.
    duration_ms = models.IntegerField(null=True, blank=True)

    tokens_used = models.IntegerField(default=0)

    # Which LLM provider handled this agent's call.
    model_provider = models.CharField(
        max_length=32,
        choices=[("groq", "Groq"), ("cerebras", "Cerebras")],
    )

    model_name = models.CharField(max_length=64)

    # First 400 chars of agent output — stored for quick debugging.
    # Full output lives in Langfuse span. Never store PII here.
    output_summary = models.TextField(null=True, blank=True)

    error = models.TextField(null=True, blank=True)

    # How many times this agent retried its LLM call (tenacity retries).
    retry_count = models.SmallIntegerField(default=0)

    class Meta:
        app_label = "research_agent"
        db_table = "ra_agent_log"
        ordering = ["started_at"]
        indexes = [
            # Fast per-session node lookup — used by history detail view
            models.Index(
                fields=["session", "agent_name"],
                name="ra_agent_log_session_agent_idx",
            ),
        ]
        constraints = [
            # One log row per agent per session (no duplicate agent entries)
            models.UniqueConstraint(
                fields=["session", "agent_name"],
                name="ra_agent_log_session_agent_unique",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"AgentLog({self.agent_name} | {self.status} | "
            f"{self.duration_ms}ms | {self.tokens_used} tokens)"
        )

    def complete(self, duration_ms: int, tokens: int, output_summary: str = "") -> None:
        """Called by each agent's run() method on successful completion."""
        from django.utils import timezone

        try:
            self.status = self.STATUS_COMPLETED
            self.completed_at = timezone.now()
            self.duration_ms = duration_ms
            self.tokens_used = tokens
            self.output_summary = output_summary[:400] if output_summary else ""
            self.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "duration_ms",
                    "tokens_used",
                    "output_summary",
                ]
            )
            logger.info(
                "research_agent.agent_log.completed",
                agent=self.agent_name,
                session_id=str(self.session_id),
                duration_ms=duration_ms,
                tokens=tokens,
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise

    def fail(self, error: str) -> None:
        """Called by BaseAgent on unrecoverable LLM failure."""
        from django.utils import timezone

        try:
            self.status = self.STATUS_FAILED
            self.completed_at = timezone.now()
            self.error = error[:1000]
            self.save(update_fields=["status", "completed_at", "error"])
            logger.error(
                "research_agent.agent_log.failed",
                agent=self.agent_name,
                session_id=str(self.session_id),
                error=error,
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise
