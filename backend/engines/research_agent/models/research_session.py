"""
engines/research_agent/models/research_session.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ResearchSession — one row per user query submission.

Lifecycle:  pending → running → completed / failed / cancelled

DB table: ra_session
"""

from __future__ import annotations

import uuid
import structlog
import sentry_sdk
from django.conf import settings
from django.db import models

from engines.research_agent.constants import SessionChannel, SessionStatus

logger = structlog.get_logger(__name__)


class ResearchSession(models.Model):
    """
    Created the moment a user submits a query.
    Updated as the LangGraph workflow progresses.
    Anonymous users (public) are allowed — user field is nullable.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # FK to existing auth_user table — nullable for anonymous users.
    # We reference settings.AUTH_USER_MODEL (not import from auth engine).
    # ZERO code changes to auth engine — only a FK pointer here.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="research_sessions",
        db_index=True,
    )

    query = models.TextField(
        help_text="Original research question submitted by the user.",
    )

    # SHA-256 hash of normalized query — used for cache deduplication (Opt #4).
    # Identical queries hit Redis cache and skip LangGraph entirely (<1s response).
    query_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text="SHA-256 of normalized query for cache lookup.",
    )

    status = models.CharField(
        max_length=20,
        default=SessionStatus.PENDING,
        choices=[
            (SessionStatus.PENDING, "Pending"),
            (SessionStatus.RUNNING, "Running"),
            (SessionStatus.COMPLETED, "Completed"),
            (SessionStatus.FAILED, "Failed"),
            (SessionStatus.CANCELLED, "Cancelled"),
        ],
        db_index=True,
    )

    # Langfuse trace ID — links this session to its full LLM trace.
    # Developer sees full trace in Langfuse dashboard.
    langfuse_trace_id = models.CharField(
        max_length=128,
        null=True,
        blank=True,
    )

    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Set on failure. Stored for debugging; never shown raw to user.",
    )

    # Set to True on browser disconnect — all agents check this flag before
    # doing any LLM work (Risk #12 / production safety field).
    cancelled = models.BooleanField(default=False)

    # Running total of tokens used across all agents in this session.
    # Used for abuse detection and cost tracking (Risk #40).
    total_tokens_used = models.IntegerField(default=0)

    # Real client IP — X-Forwarded-For aware (Render load balancer fix, Risk #34).
    # Used for anonymous rate limiting (PUBLIC_DAILY_LIMIT = 3 queries/day).
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    # ── Channel attribution (FEATURE_WHATSAPP.md §5.2) ────────────────────────
    # Which transport this session arrived through. NOT NULL with a default so
    # no session can ever be unattributed — every existing row backfills to
    # "web", and the web code path never needs to mention this field.
    # No db_index here: the composite index ["channel", "-created_at"] in Meta
    # already serves channel-only lookups via its leftmost prefix. A standalone
    # index would be pure write overhead on the engine's busiest table.
    # `db_default` is REQUIRED here, not decorative. Django's `default` is
    # Python-side only — AddField uses it to backfill, then drops the database
    # default. Any INSERT that omits this column then violates NOT NULL, which
    # is exactly what an older deploy's ORM does: its model has no `channel`
    # field, so the column never appears in its INSERT statement.
    #
    # db_default puts a real DEFAULT on the column, so the schema can be
    # migrated ahead of the code (as we do: Supabase in Phase 1, deploy in
    # Phase 8) without breaking the running release.
    # `choices` is DERIVED from SessionChannel, not restated. Together with the
    # ra_session_channel_valid constraint below (also derived), adding a
    # platform means editing constants.py alone — this file never moves again.
    channel = models.CharField(
        max_length=20,
        default=SessionChannel.WEB,
        db_default=SessionChannel.WEB,
        choices=[(c, c.title()) for c in SessionChannel.ALL],
        help_text="Transport the query came from. Existing rows are 'web'.",
    )

    # Opaque, HASHED external identity for non-web channels (e.g. SHA-256 of an
    # E.164 phone number). NULL for web — a browser session is identified by
    # `user` or `ip_address` instead.
    #
    # This lives here, rather than being looked up from the channel's own
    # tables, so the orchestrator can tag a Langfuse trace WITHOUT importing a
    # channel model. The engine core must never depend on one of its
    # transports. It is also what the rate limiter keys on for per-contact
    # quotas (3/day per phone, matching PUBLIC_DAILY_LIMIT).
    #
    # NEVER store a raw phone number or email address here (CLAUDE.md).
    # No db_index here either — covered by ["channel_ref", "-created_at"].
    channel_ref = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Hashed external identity. NULL for web sessions.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "research_agent"
        db_table = "ra_session"
        ordering = ["-created_at"]
        indexes = [
            # Fast user history queries: GET /api/v1/research/history/
            models.Index(
                fields=["user", "-created_at"], name="ra_session_user_created_idx"
            ),
            # Fast cache deduplication lookup before LangGraph runs
            models.Index(fields=["query_hash"], name="ra_session_query_hash_idx"),
            # Admin monitoring: filter by status
            models.Index(fields=["status"], name="ra_session_status_idx"),
            # Channel analytics: "WhatsApp sessions today", cost per channel.
            models.Index(
                fields=["channel", "-created_at"], name="ra_session_channel_idx"
            ),
            # Per-contact rate limiting and per-contact history lookups.
            models.Index(
                fields=["channel_ref", "-created_at"],
                name="ra_session_channel_ref_idx",
            ),
        ]
        constraints = [
            # DB-level CHECK constraint on status (Risk #27).
            # Django `choices` is Python-only validation — this enforces it at
            # the PostgreSQL level so no bad status can ever be written, even
            # via raw SQL or a future code path that bypasses the ORM.
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        SessionStatus.PENDING,
                        SessionStatus.RUNNING,
                        SessionStatus.COMPLETED,
                        SessionStatus.FAILED,
                        SessionStatus.CANCELLED,
                    ]
                ),
                name="ra_session_status_valid",
            ),
            # Same discipline as status: `choices` is Python-only validation, so
            # the allowed channels are enforced in PostgreSQL too.
            models.CheckConstraint(
                condition=models.Q(channel__in=list(SessionChannel.ALL)),
                name="ra_session_channel_valid",
            ),
            # Cross-channel consistency: a non-web session MUST carry its hashed
            # identity. Without this, a WhatsApp session could be written with a
            # NULL channel_ref — it would run fine, then be untraceable in
            # Langfuse and invisible to the per-contact rate limiter. This makes
            # that state impossible rather than merely unlikely.
            models.CheckConstraint(
                condition=models.Q(channel=SessionChannel.WEB)
                | models.Q(channel_ref__isnull=False),
                name="ra_session_channel_ref_required",
            ),
        ]

    def __str__(self) -> str:
        user_label = str(self.user_id) if self.user_id else "anonymous"
        return f"ResearchSession({self.id} | {user_label} | {self.status})"

    def mark_running(self) -> None:
        """Called by Celery task when LangGraph workflow starts."""
        try:
            self.status = SessionStatus.RUNNING
            self.save(update_fields=["status", "updated_at"])
            logger.info("research_agent.session.running", session_id=str(self.id))
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise

    def mark_completed(self, total_tokens: int = 0) -> None:
        """Called by Orchestrator after workflow_completed SSE fires."""
        from django.utils import timezone

        try:
            self.status = SessionStatus.COMPLETED
            self.total_tokens_used = total_tokens
            self.completed_at = timezone.now()
            self.save(
                update_fields=[
                    "status",
                    "total_tokens_used",
                    "completed_at",
                    "updated_at",
                ]
            )
            logger.info(
                "research_agent.session.completed",
                session_id=str(self.id),
                total_tokens=total_tokens,
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise

    def mark_failed(self, error: str) -> None:
        """Called on any unrecoverable workflow error."""
        try:
            self.status = SessionStatus.FAILED
            self.error_message = error
            self.save(update_fields=["status", "error_message", "updated_at"])
            logger.error(
                "research_agent.session.failed",
                session_id=str(self.id),
                error=error,
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise

    def mark_cancelled(self) -> None:
        """Called when user disconnects or hits Cancel."""
        try:
            self.status = SessionStatus.CANCELLED
            self.cancelled = True
            self.save(update_fields=["status", "cancelled", "updated_at"])
            logger.info("research_agent.session.cancelled", session_id=str(self.id))
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise
