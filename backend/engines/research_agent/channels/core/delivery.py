"""
engines/research_agent/channels/core/delivery.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Handing a finished report to whoever asked for it.

Same sequence on every platform:

    progress pings  →  summary  →  document (T5)  →  prompt (T6)

The report is read straight from `ResearchReport` — the row the agent wrote.
Nothing is regenerated, and nothing here knows which platform is receiving it:
text is trimmed to whatever `capabilities.max_text_chars` says, and that is the
only concession to platform difference.
"""

from __future__ import annotations

import structlog

from engines.research_agent.channels.core import progress, service
from engines.research_agent.channels.core.adapter import ChannelAdapter
from engines.research_agent.channels.core.models import ChannelContact, ChannelMessage

logger = structlog.get_logger(__name__)

FAILED_REPLY = "Sorry — that research run didn't complete. Please try asking again."

CANCELLED_REPLY = "That research was cancelled."

# Shown when a run is still going long after it should have finished. Better an
# honest apology than an acknowledgement followed by permanent silence.
TIMEOUT_REPLY = (
    "That research is taking unusually long. I've stopped waiting — "
    "please try again."
)


def contact_for_session(session) -> ChannelContact | None:
    """
    Who asked for this. Found via the inbound message that started the run,
    which `service._start_research` linked to the session.

    Returns None for a web session — correct, and the caller skips delivery.
    """
    message = (
        ChannelMessage.objects.filter(session=session, direction="inbound")
        .select_related("contact")
        .order_by("created_at")
        .first()
    )
    return message.contact if message else None


def send_progress(adapter: ChannelAdapter, contact: ChannelContact, session) -> int:
    """Send any milestone reached since the last poll. Returns how many went out."""
    messages = progress.pending_messages(str(session.id))
    for text in messages:
        service.send_text(adapter, contact, text, session=session)
    return len(messages)


def send_summary(adapter: ChannelAdapter, contact: ChannelContact, session) -> bool:
    """
    Send the executive summary and the confidence score.

    Returns False when there is no report to send — a completed session with no
    report row means something went wrong upstream, and saying nothing would
    leave the user waiting forever.
    """
    from engines.research_agent.models.research_report import ResearchReport

    report = ResearchReport.objects.filter(session=session).first()
    if report is None:
        logger.error("channel.delivery.no_report", session_id=str(session.id))
        service.send_text(adapter, contact, FAILED_REPLY, session=session)
        return False

    service.send_text(adapter, contact, _format_summary(report), session=session)
    logger.info(
        "channel.delivery.summary_sent",
        channel=adapter.name,
        session_id=str(session.id),
        word_count=report.word_count,
    )
    return True


def send_failure(
    adapter: ChannelAdapter, contact: ChannelContact, session, reason: str
):
    """Tell the user a run ended badly, rather than leaving them waiting."""
    text = {
        "failed": FAILED_REPLY,
        "cancelled": CANCELLED_REPLY,
        "timeout": TIMEOUT_REPLY,
    }.get(reason, FAILED_REPLY)
    service.send_text(adapter, contact, text, session=session)
    logger.info(
        "channel.delivery.failure_sent",
        channel=adapter.name,
        session_id=str(session.id),
        reason=reason,
    )


def _format_summary(report) -> str:
    """
    The chat-facing answer.

    Deliberately the executive summary, not the full report: ~300 words reads
    well on a phone, and the complete text travels in the document (T5). On a
    platform with a smaller cap the summary is trimmed — core does not decide
    that, `capabilities.max_text_chars` does.
    """
    body = (report.executive_summary or "").strip() or "(no summary produced)"
    parts = [f"📄 {body}"]

    if report.confidence_score is not None:
        parts.append(
            f"\n\nResearch confidence: {round(report.confidence_score * 100)}%"
        )
    if report.word_count:
        parts.append(f" · full report: {report.word_count} words")

    return "".join(parts)
