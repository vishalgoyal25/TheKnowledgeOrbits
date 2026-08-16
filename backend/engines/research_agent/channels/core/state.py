"""
engines/research_agent/channels/core/state.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The one stateful corner of the channel layer.

Everything else is message in → answer out. This has to remember that it asked
a question, and forget properly when nobody answers.

Canonical table: FEATURE_WHATSAPP.md §7.3. Written once here for every platform;
only the TRIGGER differs, and the adapter absorbs that — a button callback where
`supports_buttons` is True, the typed word EMAIL otherwise.

THE HEURISTIC THAT DOES THE WORK
    `@` present and no spaces ⇒ someone is trying to give us an address.

    That single test resolves two otherwise-ambiguous situations:
      · while awaiting an address, it separates "mistyped" from "changed mind"
      · while idle, it catches an address arriving with no pending state and
        stops it being researched — otherwise a user who taps the button, walks
        away past the TTL and comes back would spend a daily query researching
        their own email address.

NOTHING HERE EVER TRIGGERS RESEARCH
    While `awaiting_email`, every message is an address attempt. Two failures
    return the contact to idle with a plain "cancelled" — the message that
    cancels is consumed, not researched. Without the retry cap a user who
    changed their mind would be stuck for the full hour.
"""

from __future__ import annotations

import structlog
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone

from engines.research_agent.channels.core import constants as k
from engines.research_agent.channels.core import service
from engines.research_agent.channels.core.adapter import ChannelAdapter, InboundMessage
from engines.research_agent.channels.core.models import ChannelContact

logger = structlog.get_logger(__name__)

ASK_EMAIL_REPLY = "📧 Send me the email address to deliver this report to."

INVALID_EMAIL_REPLY = (
    "That doesn't look like an email address — please send it in the form "
    "you@example.com, or send anything else to cancel."
)

CANCELLED_REPLY = "Cancelled — no email sent. Send me a question whenever you're ready."

QUEUED_REPLY = "✅ Sending it to {address} now."

NO_PENDING_REPLY = (
    "I'm not waiting for an email address right now. Tap 📧 Email report "
    "under a report to have it sent to you."
)

QUOTA_REPLY = (
    "You've reached today's limit for emailed reports 🙏 Please try again " "tomorrow."
)

EXPIRED_SESSION_REPLY = (
    "I can't find that report any more. Ask the question again and I'll send "
    "you a fresh one."
)


def handle(
    adapter: ChannelAdapter,
    contact: ChannelContact,
    inbound: InboundMessage,
) -> str | None:
    """
    Advance the conversation if this message belongs to the email flow.

    Returns an outcome string when the message was CONSUMED, or None to let the
    caller treat it as an ordinary research question. Returning None is the
    normal path — most messages are just questions.
    """
    # A stale prompt is cleared before anything else, so the rest of this
    # function only ever sees live state.
    if contact.is_pending_expired:
        contact.clear_pending(reason="ttl_expired")

    if inbound.is_callback:
        return _on_button(adapter, contact, inbound)

    if contact.pending_action == k.PendingAction.AWAITING_EMAIL:
        return _on_awaiting_email(adapter, contact, inbound)

    # Idle, but the text looks like an address — the guard described above.
    if inbound.is_text and _looks_like_email(inbound.text):
        service.send_text(adapter, contact, NO_PENDING_REPLY)
        logger.info(
            "channel.state.address_without_prompt",
            channel=adapter.name,
            external_hash=contact.external_hash,
        )
        return "address_no_prompt"

    return None


def _on_button(
    adapter: ChannelAdapter, contact: ChannelContact, inbound: InboundMessage
) -> str:
    """
    A tapped prompt. `action_id` carries which report it refers to, so a user
    scrolling back to an older message gets THAT report rather than the newest.
    """
    action, _, session_id = (inbound.action_id or "").partition(":")

    if action != k.ACTION_EMAIL_REPORT:
        logger.warning(
            "channel.state.unknown_action",
            channel=adapter.name,
            action_id=inbound.action_id,
        )
        return "unknown_action"

    session = _load_session(session_id, contact)
    if session is None:
        service.send_text(adapter, contact, EXPIRED_SESSION_REPLY)
        return "session_missing"

    contact.set_pending(k.PendingAction.AWAITING_EMAIL, session)
    service.send_text(adapter, contact, ASK_EMAIL_REPLY, session=session)
    return "awaiting_email"


def _on_awaiting_email(
    adapter: ChannelAdapter, contact: ChannelContact, inbound: InboundMessage
) -> str:
    """
    We asked for an address. Everything arriving now is an address attempt —
    never a research question.
    """
    text = (inbound.text or "").strip()
    session = contact.pending_session

    if session is None:
        # State armed but the session vanished (deleted, or a partial write).
        contact.clear_pending(reason="session_missing")
        service.send_text(adapter, contact, EXPIRED_SESSION_REPLY)
        return "session_missing"

    if not _is_valid_email(text):
        contact.email_retry_count += 1
        exhausted = contact.email_retry_count > k.MAX_EMAIL_RETRIES

        if exhausted:
            contact.clear_pending(reason="retries_exhausted")
            service.send_text(adapter, contact, CANCELLED_REPLY)
            return "cancelled"

        contact.save(update_fields=["email_retry_count", "updated_at"])
        service.send_text(adapter, contact, INVALID_EMAIL_REPLY, session=session)
        return "invalid_email"

    if not _claim_email_quota(adapter.name, contact.external_hash):
        contact.clear_pending(reason="quota_exhausted")
        service.send_text(adapter, contact, QUOTA_REPLY, session=session)
        return "quota_exhausted"

    # Clear BEFORE queueing: the address is accepted, and leaving the state
    # armed would make the user's next message look like another attempt.
    session_id = str(session.id)
    contact.clear_pending(reason="email_requested")

    from engines.research_agent.tasks.channel_email_task import send_report_email

    send_report_email(session_id, text, str(contact.id))

    service.send_text(adapter, contact, QUEUED_REPLY.format(address=text))
    logger.info(
        "channel.state.email_queued",
        channel=adapter.name,
        session_id=session_id,
        external_hash=contact.external_hash,
    )
    return "email_queued"


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────


def _looks_like_email(text: str | None) -> bool:
    """
    Loose test — is this an ATTEMPT at an address?

    Deliberately not `validate_email`: 'me@gmail' is not a valid address but is
    obviously an attempt at one, and should be met with "that doesn't look
    right" rather than being researched.
    """
    value = (text or "").strip()
    return "@" in value and " " not in value and len(value) <= 254


def _is_valid_email(text: str) -> bool:
    """Strict test, using Django's own validator."""
    try:
        validate_email(text)
        return True
    except ValidationError:
        return False


def _load_session(session_id: str, contact: ChannelContact):
    """
    The report a prompt refers to.

    Falls back to this contact's most recent completed session when no id was
    carried — the keyword path on a platform without buttons, where there is no
    payload to put an id in.
    """
    from engines.research_agent.constants import SessionStatus
    from engines.research_agent.models.research_report import ResearchReport
    from engines.research_agent.models.research_session import ResearchSession

    if session_id:
        session = ResearchSession.objects.filter(pk=session_id).first()
        if session and ResearchReport.objects.filter(session=session).exists():
            return session
        return None

    for session in ResearchSession.objects.filter(
        channel=contact.channel,
        channel_ref=contact.external_hash,
        status=SessionStatus.COMPLETED,
    ).order_by("-created_at")[:5]:
        if ResearchReport.objects.filter(session=session).exists():
            return session
    return None


def _claim_email_quota(channel: str, external_hash: str) -> bool:
    """
    Count one emailed report against this contact's daily allowance.

    Implemented here rather than in `middleware/rate_limiter.py`: that file is
    shared with the web path and its channel contract is exactly one optional
    kwarg. A second concern does not belong in it.

    FAILS OPEN if Redis is down, matching every other limiter in this codebase.
    """
    key = k.EMAIL_QUOTA_KEY.format(
        channel=channel,
        external_hash=external_hash,
        day=timezone.now().date().isoformat(),
    )

    try:
        from django_redis import get_redis_connection

        conn = get_redis_connection("default")
    except Exception:
        logger.warning("channel.email.quota_redis_unavailable_fail_open")
        return True

    try:
        used = conn.incr(key)
        if used == 1:
            conn.expire(key, 24 * 3600)
    except Exception as exc:
        logger.warning("channel.email.quota_error_fail_open", error=str(exc))
        return True

    if used > k.EMAIL_DAILY_LIMIT:
        logger.info(
            "channel.email.quota_exhausted",
            channel=channel,
            external_hash=external_hash,
            used=used,
        )
        return False
    return True
