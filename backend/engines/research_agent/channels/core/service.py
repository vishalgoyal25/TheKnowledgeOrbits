"""
engines/research_agent/channels/core/service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
What happens to an inbound message, on every platform.

The webhook hands over an adapter and a normalised InboundMessage; from here
nothing knows or cares which platform it came from.

    dedupe  →  upsert contact  →  log  →  act

DEDUPE IS DONE BY THE DATABASE, NOT BY A LOOKUP
    Every provider re-delivers on retry, and two workers can receive the same
    retry simultaneously. A `filter(...).exists()` check would let both pass.
    Instead we INSERT and let the unique constraint on `provider_message_id`
    reject the loser — atomic, race-free, no locking.

OUTBOUND IS LOGGED HERE TOO
    `send_text` / `send_document` / `send_prompt` wrap the adapter so every
    message we send lands in ra_channel_message, and a blocked contact is
    deactivated once rather than in each caller. Delivery code stays thin.
"""

from __future__ import annotations

import structlog
from django.db import IntegrityError, transaction

from engines.research_agent.channels.core import constants as k
from engines.research_agent.channels.core import http
from engines.research_agent.channels.core.adapter import ChannelAdapter, InboundMessage
from engines.research_agent.channels.core.models import ChannelContact, ChannelMessage

logger = structlog.get_logger(__name__)

# Sent when someone forwards a photo, voice note or sticker. Friendlier than
# silence, and it tells the user the bot is alive and what it wants.
UNSUPPORTED_REPLY = (
    "I can only read text messages right now — send me a question and I'll "
    "research it for you."
)


# ──────────────────────────────────────────────────────────────────────────────
# INBOUND
# ──────────────────────────────────────────────────────────────────────────────


def handle_inbound(adapter: ChannelAdapter, inbound: InboundMessage) -> str:
    """
    Process one verified, parsed message.

    Returns a short status string — useful in logs and tests, ignored by the
    webhook, which always answers 200. Raising here would make the provider
    retry, which is almost never what we want for a message we already stored.
    """
    contact = _upsert_contact(adapter, inbound)

    message = _record_inbound(adapter, contact, inbound)
    if message is None:
        # The unique constraint rejected it: we have already handled this
        # update. Silence is correct — replying again would double-send.
        logger.info(
            "channel.inbound.duplicate",
            channel=adapter.name,
            provider_message_id=inbound.provider_message_id,
        )
        return "duplicate"

    contact.touch_inbound()

    if inbound.kind == k.MessageType.UNSUPPORTED:
        send_text(adapter, contact, UNSUPPORTED_REPLY)
        return "unsupported"

    # ── T2: echo, to prove the round trip ────────────────────────────────────
    # T3 replaces this with: rate limit → create ResearchSession → enqueue
    # run_research(). The seam is deliberate — everything above this line is
    # permanent, everything below it is scaffolding.
    if inbound.is_text:
        send_text(adapter, contact, inbound.text or "", session=None)
        return "echoed"

    if inbound.is_callback:
        send_text(adapter, contact, f"(button: {inbound.action_id})")
        return "callback"

    return "ignored"


def _upsert_contact(adapter: ChannelAdapter, inbound: InboundMessage) -> ChannelContact:
    """
    Find or create the contact for this identity.

    Keyed on (channel, external_id) — the same phone on two platforms is two
    contacts on purpose: separate conversations, separate pending state.

    `display_name` and `metadata` are refreshed on every message, because people
    change their username and we would otherwise show a stale one forever.
    """
    contact, created = ChannelContact.objects.get_or_create(
        channel=adapter.name,
        external_id=inbound.external_id,
        defaults={
            "external_hash": k.hash_identity(inbound.external_id),
            "display_name": inbound.display_name,
            "metadata": inbound.metadata or {},
        },
    )

    if created:
        logger.info(
            "channel.contact.created",
            channel=adapter.name,
            external_hash=contact.external_hash,
        )
        return contact

    changed = []
    if inbound.display_name and inbound.display_name != contact.display_name:
        contact.display_name = inbound.display_name
        changed.append("display_name")
    if inbound.metadata and inbound.metadata != contact.metadata:
        contact.metadata = {**(contact.metadata or {}), **inbound.metadata}
        changed.append("metadata")
    if changed:
        contact.save(update_fields=[*changed, "updated_at"])

    return contact


def _record_inbound(
    adapter: ChannelAdapter, contact: ChannelContact, inbound: InboundMessage
) -> ChannelMessage | None:
    """
    Store the inbound message, or return None if it is a re-delivery.

    The INSERT itself is the dedupe: `provider_message_id` is unique, so a
    duplicate raises IntegrityError instead of racing a lookup.

    Wrapped in its own atomic block because a failed INSERT poisons the
    surrounding transaction in PostgreSQL — without this, everything after
    would fail too.
    """
    try:
        with transaction.atomic():
            return ChannelMessage.objects.create(
                contact=contact,
                channel=adapter.name,
                direction=k.Direction.INBOUND,
                provider_message_id=inbound.provider_message_id,
                message_type=inbound.kind,
                body=(inbound.text or inbound.action_id or "")[:4000] or None,
                status=k.MessageStatus.RECEIVED,
                payload=inbound.metadata or {},
            )
    except IntegrityError:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# OUTBOUND — adapter call + audit row, in one place
# ──────────────────────────────────────────────────────────────────────────────


def send_text(
    adapter: ChannelAdapter,
    contact: ChannelContact,
    text: str,
    session=None,
) -> str | None:
    """Send text, truncated to what this platform accepts, and log it."""
    body = _truncate(text, adapter.capabilities.max_text_chars)
    return _send(
        adapter,
        contact,
        session,
        kind=k.MessageType.TEXT,
        body=body,
        perform=lambda: adapter.send_text(contact.external_id, body),
    )


def send_document(
    adapter: ChannelAdapter,
    contact: ChannelContact,
    url: str,
    filename: str,
    caption: str | None = None,
    session=None,
) -> str | None:
    """Send a document by public URL, and log it."""
    return _send(
        adapter,
        contact,
        session,
        kind=k.MessageType.DOCUMENT,
        body=filename,
        perform=lambda: adapter.send_document(
            contact.external_id, url, filename, caption
        ),
    )


def send_prompt(
    adapter: ChannelAdapter,
    contact: ChannelContact,
    text: str,
    action_id: str,
    session=None,
) -> str | None:
    """
    Ask something actionable.

    Core sends the same `action_id` everywhere. A platform with buttons renders
    a tappable one; a platform without appends a keyword instruction. That
    branch is the ADAPTER's — the only thing core reads is the capability flag,
    and only to decide what the text should say.
    """
    if not adapter.capabilities.supports_buttons:
        text = f"{text}\n\nReply {k.EMAIL_KEYWORD} to continue."
    body = _truncate(text, adapter.capabilities.max_text_chars)
    return _send(
        adapter,
        contact,
        session,
        kind=k.MessageType.PROMPT,
        body=body,
        perform=lambda: adapter.send_prompt(contact.external_id, body, action_id),
    )


def _send(
    adapter: ChannelAdapter,
    contact: ChannelContact,
    session,
    *,
    kind: str,
    body: str | None,
    perform,
) -> str | None:
    """
    One outbound send: refuse if inactive, call the adapter, write the audit row.

    Never raises. A send failure must not take down a worker mid-delivery —
    the failure is logged, recorded on the message row, and the caller decides
    whether the rest of the sequence is still worth attempting.
    """
    if not contact.is_active:
        logger.info(
            "channel.send.skipped_inactive",
            channel=adapter.name,
            external_hash=contact.external_hash,
        )
        return None

    provider_id = None
    status = k.MessageStatus.SENT
    error = None

    try:
        provider_id = perform()
        if provider_id is None:
            # The budget guard refused. Not an error, but nothing was sent.
            status = k.MessageStatus.FAILED
            error = "budget_exhausted"
    except http.ChannelBlockedError as exc:
        # The user blocked the bot. Stop talking to them; never retry.
        contact.deactivate(reason="blocked_by_user")
        status = k.MessageStatus.FAILED
        error = str(exc)[:500]
    except http.ChannelSendError as exc:
        status = k.MessageStatus.FAILED
        error = str(exc)[:500]

    ChannelMessage.objects.create(
        contact=contact,
        channel=adapter.name,
        session=session,
        direction=k.Direction.OUTBOUND,
        provider_message_id=(
            f"{adapter.name}:out:{provider_id}" if provider_id else None
        ),
        message_type=kind,
        body=(body or "")[:4000] or None,
        status=status,
        error=error,
    )

    return provider_id


def _truncate(text: str, limit: int) -> str:
    """Fit a message to the platform's cap, with a visible marker if cut."""
    value = text or ""
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"
