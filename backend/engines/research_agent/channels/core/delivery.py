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

import re

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


def send_document(adapter: ChannelAdapter, contact: ChannelContact, session) -> bool:
    """
    Send the full report as a file.

    The provider fetches it from the EXISTING export endpoint — the same URL the
    browser's download button uses. We never render a second copy and never hold
    bytes in memory: one media path, as required by CLAUDE.md.

    On an UPLOAD platform we choose the filename the user sees; on a URL platform
    the provider takes it from the endpoint's `Content-Disposition`
    (`research-<id>.pdf`) and this name is advisory.

    FORMATS ARE TRIED IN ORDER, PDF THEN MARKDOWN
        `_export_format()` only proves WeasyPrint IMPORTS — not that it renders.
        A font problem or a malformed table makes `export_service` raise
        `pdf_render_failed`, `ExportView` answer 503, and the fetch fail. Without
        a second attempt the user would get a summary and no document at all.

        Markdown needs no rendering, so it is the floor: whatever else breaks,
        something readable arrives. Production degrades exactly the way local
        already behaves.
    """
    from engines.research_agent.channels.core import constants as k

    if not k.BACKEND_PUBLIC_URL:
        # Both paths need it — a URL platform fetches it, and we fetch it
        # ourselves before uploading. A blank value fails far from here.
        logger.error("channel.delivery.no_public_url", session_id=str(session.id))
        return False

    for fmt in _format_candidates():
        result = service.send_document(
            adapter,
            contact,
            url=k.export_url(str(session.id), fmt),
            filename=_document_filename(session, fmt),
            caption=None,
            session=session,
        )
        if result is not None:
            logger.info(
                "channel.delivery.document_sent",
                channel=adapter.name,
                session_id=str(session.id),
                export_format=fmt,
            )
            return True

        logger.warning(
            "channel.delivery.document_format_failed",
            channel=adapter.name,
            session_id=str(session.id),
            export_format=fmt,
        )

    logger.error(
        "channel.delivery.document_failed_all_formats",
        channel=adapter.name,
        session_id=str(session.id),
    )
    return False


def _format_candidates() -> tuple[str, ...]:
    """
    Formats to attempt, best first.

    Where PDF is possible it is preferred and Markdown is the safety net. Where
    it is not (local dev), attempting it would waste a request on a 503 we can
    already predict.
    """
    return ("pdf", "md") if _export_format() == "pdf" else ("md",)


def _document_filename(session, fmt: str) -> str:
    """
    A filename a person can recognise in a chat thread.

    `sixteenth-finance-commission.md` beats `research-282191b0.md` when you are
    scrolling back through a conversation looking for one report. Falls back to
    the session-id form if the query slugifies to nothing (non-Latin script,
    punctuation only).
    """
    slug = re.sub(r"[^a-z0-9]+", "-", (session.query or "").lower()).strip("-")[:48]
    slug = slug.strip("-")
    return f"{slug or 'research-' + str(session.id)[:8]}.{fmt}"


_EXPORT_FORMAT: str | None = None


def _export_format() -> str:
    """
    'pdf' where WeasyPrint exists, 'md' otherwise.

    WeasyPrint is production-only (`requirements/prod.txt`) and needs system
    libraries usually absent on Windows, so local development delivers Markdown.
    Without this fallback the whole local loop would be untestable and the gap
    would only surface after deploying.

    Probing the import mirrors what `export_service._html_to_pdf` does, and is
    far cheaper than rendering a PDF just to discover it cannot be rendered.
    Cached because the answer cannot change while the process lives.
    """
    global _EXPORT_FORMAT
    if _EXPORT_FORMAT is None:
        try:
            import weasyprint  # noqa: F401

            _EXPORT_FORMAT = "pdf"
        except Exception:
            _EXPORT_FORMAT = "md"
            logger.info("channel.delivery.pdf_unavailable_using_markdown")
    return _EXPORT_FORMAT


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
