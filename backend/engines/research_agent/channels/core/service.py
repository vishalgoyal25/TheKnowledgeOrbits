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

import hashlib

import sentry_sdk
import structlog
from django.db import IntegrityError, transaction
from django.utils import timezone

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

# Sent the moment a run is queued, and then it IS quiet for 40–90s — the single
# worker is busy with the workflow itself, so nothing can be sent mid-run.
# The ack therefore has to carry the expectation on its own: how long, and what
# will arrive. Silence you were warned about reads as working; unexplained
# silence reads as broken.
ACK_REPLY = (
    "🔍 Researching now — this takes about a minute.\n\n"
    "I'll send a summary, the full report as a file, and the option to email it."
)

# Same daily allowance as an anonymous web visitor (PUBLIC_DAILY_LIMIT), but
# counted per contact rather than per IP.
RATE_LIMIT_REPLY = (
    "You've used your research queries for today 🙏\n\n" "Please try again in 24 hours."
)

ERROR_REPLY = "Something went wrong starting that research. Please try again."

# Sent when an identical question was researched recently. Saying so is honest —
# otherwise an instant answer looks like the bot skipped the work.
REUSED_REPLY = "⚡ I researched this recently — here's that report:"


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

    if inbound.is_callback:
        # Dismiss the platform's "processing" indicator. A default no-op on
        # platforms that have no such concept.
        adapter.acknowledge(inbound)

    # The email conversation gets first refusal. It consumes a message only
    # when one genuinely belongs to it — a button tap, an address we asked for,
    # or an address nobody asked for. Otherwise it returns None and the message
    # is an ordinary question.
    from engines.research_agent.channels.core import state

    outcome = state.handle(adapter, contact, inbound)
    if outcome is not None:
        return outcome

    if not inbound.is_text:
        return "ignored"

    return _start_research(adapter, contact, inbound, message)


def _start_research(
    adapter: ChannelAdapter,
    contact: ChannelContact,
    inbound: InboundMessage,
    message: ChannelMessage,
) -> str:
    """
    Turn a chat message into a real research run.

    Deliberately mirrors QueryView so a channel session is indistinguishable
    from a web one downstream: same model, same status, same hash, same task.
    All five ops tables, Langfuse and DeepEval then populate identically —
    that equivalence is the whole point of the channel layer.

    Two differences, both required:
      · the rate limiter is keyed on the contact's HASH, not our server's IP
      · `channel` / `channel_ref` are set, so the run is attributable

    Repeat questions reuse an earlier SESSION rather than the Redis query cache.
    The cache stores a report blob with no session id, and with no session there
    is nothing to export a document from — so a cached answer could never carry
    a PDF. Reusing the session gives the same instant reply AND a working
    document (FEATURE_WHATSAPP.md §6.3, resolved).
    """
    from engines.research_agent.constants import SessionStatus
    from engines.research_agent.middleware.rate_limiter import rate_limiter
    from engines.research_agent.models.research_session import ResearchSession
    from engines.research_agent.tasks.channel_delivery_task import deliver_when_ready

    query = (inbound.text or "").strip()

    # Same normalisation as QueryView, so a question asked on the website and
    # in a chat app share a cache key and read as the same query in analytics.
    query_hash = hashlib.sha256(query.lower().encode("utf-8")).hexdigest()

    # ── Reuse a recent identical answer ──────────────────────────────────────
    # Checked BEFORE the rate limit, matching QueryView: an answer we already
    # have should not cost the user one of their three daily questions.
    reusable = _recent_completed_session(query_hash)
    if reusable is not None:
        message.session = reusable
        message.save(update_fields=["session"])

        send_text(adapter, contact, REUSED_REPLY, session=reusable)
        # instant=True skips the progress pings — there is no work to narrate.
        deliver_when_ready(str(reusable.id), instant=True, schedule=0)

        logger.info(
            "channel.query.reused_session",
            channel=adapter.name,
            session_id=str(reusable.id),
            age_seconds=int((timezone.now() - reusable.created_at).total_seconds()),
        )
        return "reused"

    # Keyed on the hashed identity: every channel request arrives from OUR
    # server, so an IP-keyed limit would put all bot users in one bucket.
    allowed, remaining = rate_limiter.check_query_limit(
        ip=None,
        is_authenticated=False,
        identity_override=f"{adapter.name}:{contact.external_hash}",
    )
    if not allowed:
        logger.info(
            "channel.query.rate_limited",
            channel=adapter.name,
            external_hash=contact.external_hash,
        )
        send_text(adapter, contact, RATE_LIMIT_REPLY)
        return "rate_limited"

    try:
        session = ResearchSession.objects.create(
            user=None,
            query=query,
            query_hash=query_hash,
            status=SessionStatus.PENDING,
            channel=adapter.name,
            channel_ref=contact.external_hash,
        )
    except Exception as exc:
        logger.error(
            "channel.query.create_failed", channel=adapter.name, error=str(exc)
        )
        sentry_sdk.capture_exception(exc)
        send_text(adapter, contact, ERROR_REPLY)
        return "create_failed"

    # Link the inbound message to the run it started, so the audit trail joins
    # up: message → session → report → agent logs → evaluation.
    message.session = session
    message.save(update_fields=["session"])

    # Off the request thread and onto the worker.
    from engines.research_agent.tasks.research_task import run_research

    run_research(str(session.id))

    # A second task watches that run and delivers the result. It polls by
    # re-enqueueing itself rather than waiting, because a blocking watcher
    # would occupy the single worker and starve the research task it is
    # waiting for.
    from engines.research_agent.tasks.channel_delivery_task import deliver_when_ready

    deliver_when_ready(str(session.id))

    send_text(adapter, contact, ACK_REPLY, session=session)

    logger.info(
        "channel.query.queued",
        channel=adapter.name,
        session_id=str(session.id),
        external_hash=contact.external_hash,
        remaining=remaining,
    )
    return "queued"


def _recent_completed_session(query_hash: str):
    """
    A finished run for this exact question, recent enough to still be current.

    Deliberately channel-agnostic: a question answered on the website is reused
    for a chat user and vice versa. The report is generic research content, and
    this is exactly what the existing Redis query cache already does for web.

    The window matches `QUERY_CACHE_TTL`, so chat and web consider an answer
    stale at the same moment.

    A session is only reusable if a report actually exists — a COMPLETED session
    without one would deliver silence.
    """
    from datetime import timedelta

    from engines.research_agent.constants import QUERY_CACHE_TTL, SessionStatus
    from engines.research_agent.models.research_report import ResearchReport
    from engines.research_agent.models.research_session import ResearchSession

    cutoff = timezone.now() - timedelta(seconds=QUERY_CACHE_TTL)

    candidates = ResearchSession.objects.filter(
        query_hash=query_hash,
        status=SessionStatus.COMPLETED,
        created_at__gte=cutoff,
    ).order_by("-created_at")[:5]

    for session in candidates:
        if ResearchReport.objects.filter(session=session).exists():
            return session
    return None


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
