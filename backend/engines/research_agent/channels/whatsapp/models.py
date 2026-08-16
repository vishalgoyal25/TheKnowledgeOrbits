"""
engines/research_agent/channels/whatsapp/models.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WhatsApp channel tables. Three models, all declared with
`app_label = "research_agent"` so they live in the engine's own migration
history — no new Django app, no cross-engine FK.

  ra_wa_contact     one row per phone number that has ever messaged us
  ra_wa_message     inbound/outbound audit log (idempotency lives here)
  ra_report_delivery  one row per attempt to hand a report to a user

These are ADDITIVE. The 5 existing ops tables are untouched: a WhatsApp query
creates a normal ResearchSession, so ResearchReport, AgentExecutionLog,
AgentStateSnapshot and EvaluationResult populate exactly as they do for web
(FEATURE_WHATSAPP.md §5).

PII: the raw phone number lives ONLY in ra_wa_contact, because we need it to
reply. `phone_hash` is what travels to ResearchSession.channel_ref, Langfuse
and Sentry — never the raw number (CLAUDE.md).
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import sentry_sdk
import structlog
from django.db import models
from django.utils import timezone

from engines.research_agent.channels.whatsapp import config

logger = structlog.get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# CHOICES — plain string constants, mirroring engines/research_agent/constants.py
# ──────────────────────────────────────────────────────────────────────────────


class Direction:
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    ALL = (INBOUND, OUTBOUND)


class MessageType:
    TEXT = "text"
    INTERACTIVE = "interactive"
    DOCUMENT = "document"
    UNSUPPORTED = "unsupported"  # audio/image/location/etc — logged, then declined
    ALL = (TEXT, INTERACTIVE, DOCUMENT, UNSUPPORTED)


class MessageStatus:
    RECEIVED = "received"
    SENT = "sent"
    FAILED = "failed"
    ALL = (RECEIVED, SENT, FAILED)


class PendingAction:
    """Conversation state. NULL means idle (FEATURE_WHATSAPP.md §7.3)."""

    AWAITING_EMAIL = "awaiting_email"
    ALL = (AWAITING_EMAIL,)


# DeliveryChannel / DeliveryStatus moved to channels/core/constants.py with
# ReportDelivery (T1.1). The enums below stay because WhatsAppContact and
# WhatsAppMessage still use them; this whole module is superseded by core and
# is retained only until the WhatsApp adapter is rebuilt.


# ──────────────────────────────────────────────────────────────────────────────
# CONTACT
# ──────────────────────────────────────────────────────────────────────────────


class WhatsAppContact(models.Model):
    """
    One row per phone number. Created on first inbound message — that message
    IS the opt-in, and it is also what opens the 24-hour service window.

    Also holds the email state machine (§7.3). The three `pending_*` fields move
    together: they are set as a group and cleared to NULL as a group.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # E.164, e.g. "919876543210". PII — never leaves this table.
    phone_e164 = models.CharField(max_length=20, unique=True)

    # SHA-256 of the number. This is the ONLY identifier allowed to travel to
    # ResearchSession.channel_ref, Langfuse and Sentry.
    phone_hash = models.CharField(max_length=64, db_index=True)

    display_name = models.CharField(
        max_length=120,
        null=True,
        blank=True,
        help_text="WhatsApp profile name, if Meta sends one. Cosmetic only.",
    )

    # Sending to a contact who has opted out is a hard stop.
    opted_in = models.BooleanField(default=True)

    # Drives the 24-hour free-messaging window (FEATURE_WHATSAPP.md §4).
    last_inbound_at = models.DateTimeField(null=True, blank=True)

    # ── Email state machine — all three are set and cleared together ──────────
    pending_action = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        choices=[(PendingAction.AWAITING_EMAIL, "Awaiting email")],
        help_text="NULL = idle.",
    )
    pending_session = models.ForeignKey(
        "research_agent.ResearchSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Which report the pending action refers to.",
    )
    pending_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "WhatsApp has no 'dismiss' event for an inline button, so a walked-"
            "away user is unstuck by this TTL rather than by a close signal."
        ),
    )
    email_retry_count = models.SmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "research_agent"
        db_table = "ra_wa_contact"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["phone_hash"], name="ra_wa_contact_hash_idx"),
            models.Index(fields=["pending_action"], name="ra_wa_contact_pending_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(pending_action__isnull=True)
                | models.Q(pending_action__in=list(PendingAction.ALL)),
                name="ra_wa_contact_pending_action_valid",
            ),
        ]

    def __str__(self) -> str:
        state = self.pending_action or "idle"
        return f"WhatsAppContact({self.phone_hash[:8]}… | {state})"

    # ── State machine helpers ────────────────────────────────────────────────
    @property
    def is_pending_expired(self) -> bool:
        """True when a pending action exists but its TTL has passed."""
        if not self.pending_action or self.pending_expires_at is None:
            return False
        return timezone.now() >= self.pending_expires_at

    def set_awaiting_email(self, session) -> None:
        """User tapped the email button — arm the state with a TTL."""
        try:
            self.pending_action = PendingAction.AWAITING_EMAIL
            self.pending_session = session
            self.pending_expires_at = timezone.now() + timedelta(
                minutes=config.PENDING_ACTION_TTL_MINUTES
            )
            self.email_retry_count = 0
            self.save(
                update_fields=[
                    "pending_action",
                    "pending_session",
                    "pending_expires_at",
                    "email_retry_count",
                    "updated_at",
                ]
            )
            logger.info(
                "whatsapp.contact.awaiting_email",
                phone_hash=self.phone_hash,
                session_id=str(session.id),
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise

    def clear_pending(self, reason: str = "done") -> None:
        """
        Return to idle — every pending field back to NULL.

        The single exit for all four abandon paths in §7.3: sent, gave up after
        retries, user asked something else, TTL expired.
        """
        try:
            self.pending_action = None
            self.pending_session = None
            self.pending_expires_at = None
            self.email_retry_count = 0
            self.save(
                update_fields=[
                    "pending_action",
                    "pending_session",
                    "pending_expires_at",
                    "email_retry_count",
                    "updated_at",
                ]
            )
            logger.info(
                "whatsapp.contact.pending_cleared",
                phone_hash=self.phone_hash,
                reason=reason,
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise

    def touch_inbound(self) -> None:
        """Record an inbound message — this is what reopens the 24h window."""
        try:
            self.last_inbound_at = timezone.now()
            self.save(update_fields=["last_inbound_at", "updated_at"])
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise


# ──────────────────────────────────────────────────────────────────────────────
# MESSAGE
# ──────────────────────────────────────────────────────────────────────────────


class WhatsAppMessage(models.Model):
    """
    Audit log of every message in either direction.

    `wa_message_id` is the idempotency key: Meta re-delivers webhooks on retry,
    so a duplicate insert must be rejected rather than run the agent twice.
    It is unique BUT nullable — Postgres permits many NULLs, which is what we
    want for outbound rows whose send failed before Meta returned an id.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    contact = models.ForeignKey(
        WhatsAppContact,
        on_delete=models.CASCADE,
        related_name="messages",
    )

    # Set for inbound messages that started research, and for the outbound
    # messages that carry its results. NULL for greetings, errors, help text.
    session = models.ForeignKey(
        "research_agent.ResearchSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_messages",
    )

    direction = models.CharField(
        max_length=10,
        choices=[(Direction.INBOUND, "Inbound"), (Direction.OUTBOUND, "Outbound")],
        db_index=True,
    )

    wa_message_id = models.CharField(
        max_length=128,
        unique=True,
        null=True,
        blank=True,
        help_text="Meta's message id. Idempotency key for inbound.",
    )

    message_type = models.CharField(
        max_length=20,
        default=MessageType.TEXT,
        choices=[(t, t.title()) for t in MessageType.ALL],
    )

    body = models.TextField(
        null=True,
        blank=True,
        help_text="Text content, truncated. NULL for documents.",
    )

    status = models.CharField(
        max_length=10,
        default=MessageStatus.RECEIVED,
        choices=[(s, s.title()) for s in MessageStatus.ALL],
        db_index=True,
    )

    error = models.TextField(null=True, blank=True)

    # Full webhook/response envelope. Invaluable when Meta changes a payload
    # shape and nothing else explains the failure.
    payload = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "research_agent"
        db_table = "ra_wa_message"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["contact", "-created_at"], name="ra_wa_msg_contact_idx"
            ),
            models.Index(fields=["session"], name="ra_wa_msg_session_idx"),
            models.Index(fields=["wa_message_id"], name="ra_wa_msg_waid_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(direction__in=list(Direction.ALL)),
                name="ra_wa_message_direction_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=list(MessageStatus.ALL)),
                name="ra_wa_message_status_valid",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"WhatsAppMessage({self.direction} | {self.message_type} | {self.status})"
        )


# ──────────────────────────────────────────────────────────────────────────────
# DELIVERY — moved to channels/core/models.py during the core extraction (T1.1)
# ──────────────────────────────────────────────────────────────────────────────
# ReportDelivery was never WhatsApp-specific: every channel delivers reports and
# only `destination` differs. It now lives in core with a FK to ChannelContact,
# so Telegram and every future platform share one delivery audit trail.
#
# Same class name, same app_label, same db_table (ra_report_delivery) — the move
# is invisible to migrations apart from the contact FK being retargeted.
