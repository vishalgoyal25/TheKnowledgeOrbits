"""
engines/research_agent/channels/core/models.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Generic channel storage. Three tables, no platform anywhere in them.

    ra_channel_contact    one row per (channel, external_id)
    ra_channel_message    inbound/outbound audit log; idempotency lives here
    ra_report_delivery    one row per attempt to hand a report to someone

WHY GENERIC
    The email state machine is core, and it reads and writes `pending_action`.
    If each platform owned its own contact table, core could not operate on it —
    you would need one state machine per platform, which is the duplication this
    architecture exists to prevent.

    Every platform has "a person we are talking to" and "a message". Only the
    SHAPE of the identity differs — a phone number, a chat id, a workspace user
    id — and that is just a string in `external_id`. Anything genuinely
    platform-specific goes in `metadata` (JSON), which core never reads.

    Consequence: adding platform #11 needs NO new table and NO new column.

DELIBERATELY NO CHANNEL CHECK CONSTRAINT HERE
    `ra_session` and `ra_report_delivery` carry DB-level allow-lists, because
    those are the rows analytics and billing hang off. Adding a third here would
    make every new platform a 3-operation migration instead of 2, for a table
    that is always written through core. Validated in Python instead.

PII
    Raw identities live ONLY in ra_channel_contact.external_id. `external_hash`
    is what reaches ResearchSession.channel_ref, Langfuse and Sentry.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import sentry_sdk
import structlog
from django.db import models
from django.utils import timezone

from engines.research_agent.channels.core import constants as k

logger = structlog.get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# CONTACT
# ──────────────────────────────────────────────────────────────────────────────


class ChannelContact(models.Model):
    """
    Someone who has messaged us on some platform.

    Created on first inbound message — that message IS the opt-in. Also holds
    the email state machine: the three `pending_*` fields plus the retry
    counter move together, always, and are cleared together.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    channel = models.CharField(
        max_length=20,
        db_index=True,
        help_text="A SessionChannel value: telegram, whatsapp, …",
    )

    # Raw identity: chat_id, phone in E.164, platform user id. PII — this is
    # the only place it exists.
    external_id = models.CharField(max_length=128)

    # Keyed hash of external_id. The ONLY identifier allowed to travel to
    # ResearchSession.channel_ref, Langfuse and Sentry.
    external_hash = models.CharField(max_length=64, db_index=True)

    display_name = models.CharField(
        max_length=120,
        null=True,
        blank=True,
        help_text="Profile name if the platform sends one. Cosmetic only.",
    )

    # False after the user blocks the bot or opts out. Sending is a hard stop.
    is_active = models.BooleanField(default=True)

    last_inbound_at = models.DateTimeField(null=True, blank=True)

    # ── Email state machine — set together, cleared together ─────────────────
    pending_action = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        choices=[(k.PendingAction.AWAITING_EMAIL, "Awaiting email")],
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
            "No platform emits a 'user dismissed this' event, so a TTL is the "
            "only way a walked-away user gets unstuck."
        ),
    )
    email_retry_count = models.SmallIntegerField(default=0)

    # Platform extras — Telegram username/language, WhatsApp wa_id, etc.
    # Written by an adapter, never read by core.
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "research_agent"
        db_table = "ra_channel_contact"
        ordering = ["-updated_at"]
        constraints = [
            # One row per person per platform. The same phone on WhatsApp and
            # Telegram is two contacts, correctly — different conversations.
            models.UniqueConstraint(
                fields=["channel", "external_id"],
                name="ra_channel_contact_identity_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(pending_action__isnull=True)
                | models.Q(pending_action__in=list(k.PendingAction.ALL)),
                name="ra_channel_contact_pending_action_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["external_hash"], name="ra_ch_contact_hash_idx"),
            models.Index(
                fields=["channel", "pending_action"], name="ra_ch_contact_pending_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"ChannelContact({self.channel}:{self.external_hash[:8]}… | {self.pending_action or 'idle'})"

    # ── State machine helpers ────────────────────────────────────────────────
    @property
    def is_pending_expired(self) -> bool:
        """True when a pending action exists but its TTL has passed."""
        if not self.pending_action or self.pending_expires_at is None:
            return False
        return timezone.now() >= self.pending_expires_at

    def set_pending(self, action: str, session) -> None:
        """Arm a pending action with a TTL. The only writer of these fields."""
        try:
            self.pending_action = action
            self.pending_session = session
            self.pending_expires_at = timezone.now() + timedelta(
                minutes=k.PENDING_ACTION_TTL_MINUTES
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
                "channel.contact.pending_set",
                channel=self.channel,
                external_hash=self.external_hash,
                action=action,
                session_id=str(getattr(session, "id", None)),
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise

    def clear_pending(self, reason: str = "done") -> None:
        """
        Back to idle — every pending field to NULL.

        The single exit for all four abandon paths: delivered, gave up after
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
                "channel.contact.pending_cleared",
                channel=self.channel,
                external_hash=self.external_hash,
                reason=reason,
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise

    def touch_inbound(self) -> None:
        """Record an inbound message. Also reactivates a previously blocked contact."""
        try:
            self.last_inbound_at = timezone.now()
            self.is_active = True
            self.save(update_fields=["last_inbound_at", "is_active", "updated_at"])
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise

    def deactivate(self, reason: str = "blocked") -> None:
        """The user blocked the bot. Stop sending; do not retry."""
        try:
            self.is_active = False
            self.save(update_fields=["is_active", "updated_at"])
            logger.info(
                "channel.contact.deactivated",
                channel=self.channel,
                external_hash=self.external_hash,
                reason=reason,
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise


# ──────────────────────────────────────────────────────────────────────────────
# MESSAGE
# ──────────────────────────────────────────────────────────────────────────────


class ChannelMessage(models.Model):
    """
    Every message in either direction, on any platform.

    `provider_message_id` is the idempotency key. Providers re-deliver webhooks
    on retry, so a duplicate must be rejected rather than run the agent twice.
    Unique BUT nullable — Postgres permits many NULLs, which is what we want for
    outbound rows whose send failed before the provider returned an id.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    contact = models.ForeignKey(
        ChannelContact,
        on_delete=models.CASCADE,
        related_name="messages",
    )

    # Denormalised from contact so channel-scoped queries need no join.
    channel = models.CharField(max_length=20, db_index=True)

    # Set for the inbound message that started research and the outbound ones
    # carrying its results. NULL for greetings, errors and help text.
    session = models.ForeignKey(
        "research_agent.ResearchSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="channel_messages",
    )

    direction = models.CharField(
        max_length=10,
        choices=[(d, d.title()) for d in k.Direction.ALL],
        db_index=True,
    )

    provider_message_id = models.CharField(
        max_length=128,
        unique=True,
        null=True,
        blank=True,
        help_text="The provider's message id. Idempotency key for inbound.",
    )

    message_type = models.CharField(
        max_length=20,
        default=k.MessageType.TEXT,
        choices=[(t, t.title()) for t in k.MessageType.ALL],
    )

    body = models.TextField(
        null=True,
        blank=True,
        help_text="Text content, truncated. NULL for documents.",
    )

    status = models.CharField(
        max_length=10,
        default=k.MessageStatus.RECEIVED,
        choices=[(s, s.title()) for s in k.MessageStatus.ALL],
        db_index=True,
    )

    error = models.TextField(null=True, blank=True)

    # Raw envelope. Invaluable when a provider changes a payload shape and
    # nothing else explains why parsing broke.
    payload = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "research_agent"
        db_table = "ra_channel_message"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["contact", "-created_at"], name="ra_ch_msg_contact_idx"
            ),
            models.Index(fields=["session"], name="ra_ch_msg_session_idx"),
            models.Index(fields=["provider_message_id"], name="ra_ch_msg_provider_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(direction__in=list(k.Direction.ALL)),
                name="ra_channel_message_direction_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=list(k.MessageStatus.ALL)),
                name="ra_channel_message_status_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"ChannelMessage({self.channel} | {self.direction} | {self.status})"


# ──────────────────────────────────────────────────────────────────────────────
# DELIVERY
# ──────────────────────────────────────────────────────────────────────────────


class ReportDelivery(models.Model):
    """
    One row per attempt to hand a finished report to a user, on any channel.

    A row rather than a column on the session, because one report can be
    delivered repeatedly — to Telegram, then to two different email addresses,
    with one of them failing. A column cannot express that, and this audit trail
    is exactly what you want when a user says "I never got it".

    Moved here from channels/whatsapp/models.py during the core extraction.
    Same class name, same app_label, same db_table — invisible to migrations
    apart from the contact FK, which now points at the generic contact.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    session = models.ForeignKey(
        "research_agent.ResearchSession",
        on_delete=models.CASCADE,
        related_name="deliveries",
    )

    contact = models.ForeignKey(
        ChannelContact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deliveries",
    )

    channel = models.CharField(
        max_length=20,
        choices=[(c, c.title()) for c in k.DeliveryChannel.ALL],
        db_index=True,
    )

    # Phone, chat id, or email address. PII — never sent to Langfuse/Sentry.
    destination = models.CharField(max_length=254)

    export_format = models.CharField(
        max_length=8,
        default="pdf",
        help_text="'pdf' normally; 'md' when WeasyPrint is unavailable (local dev).",
    )

    status = models.CharField(
        max_length=10,
        default=k.DeliveryStatus.PENDING,
        choices=[(s, s.title()) for s in k.DeliveryStatus.ALL],
        db_index=True,
    )

    error = models.TextField(null=True, blank=True)

    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "research_agent"
        db_table = "ra_report_delivery"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["session", "-created_at"], name="ra_delivery_session_idx"
            ),
            models.Index(fields=["status"], name="ra_delivery_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(channel__in=list(k.DeliveryChannel.ALL)),
                name="ra_delivery_channel_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=list(k.DeliveryStatus.ALL)),
                name="ra_delivery_status_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"ReportDelivery({self.channel} | {self.status} | {self.export_format})"

    def mark_sent(self) -> None:
        try:
            self.status = k.DeliveryStatus.SENT
            self.sent_at = timezone.now()
            self.save(update_fields=["status", "sent_at"])
            logger.info(
                "channel.delivery.sent",
                session_id=str(self.session_id),
                channel=self.channel,
                export_format=self.export_format,
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise

    def mark_failed(self, error: str) -> None:
        try:
            self.status = k.DeliveryStatus.FAILED
            self.error = error
            self.save(update_fields=["status", "error"])
            logger.error(
                "channel.delivery.failed",
                session_id=str(self.session_id),
                channel=self.channel,
                error=error,
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise
