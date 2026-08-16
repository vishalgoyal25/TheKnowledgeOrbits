"""
engines/research_agent/channels/core/delivery.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Handing a finished report to whoever asked for it.

Same sequence on every platform:

    summary (+ work log)  →  document  →  email prompt

The report is read straight from `ResearchReport` — the row the agent wrote.
Nothing is regenerated, and nothing here knows which platform is receiving it:
text is trimmed to whatever `capabilities.max_text_chars` says, and that is the
only concession to platform difference.

NO LIVE PROGRESS MESSAGES — AND WHY
    The design called for three pings during the run. They cannot work: the
    background worker processes ONE task at a time, so `run_research` holds it
    for the entire 60–90s and the delivery task cannot interleave. Under test
    all three "progress" messages arrived seconds before the report, in the
    present tense, claiming to search when searching was long finished.

    Replaced by one past-tense work log attached to the summary. Live progress
    would need a second worker on its own queue — a real infrastructure change
    (`render.yaml` is frozen), not a code change.
"""

from __future__ import annotations

import re

import structlog

from engines.research_agent.channels.core import service
from engines.research_agent.channels.core.adapter import ChannelAdapter
from engines.research_agent.channels.core.models import ChannelContact, ChannelMessage

logger = structlog.get_logger(__name__)

FAILED_REPLY = "Sorry — that research run didn't complete. Please try asking again."

CANCELLED_REPLY = "That research was cancelled."

EMAIL_PROMPT = "Want this report in your inbox?"

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


def send_email_prompt(
    adapter: ChannelAdapter, contact: ChannelContact, session
) -> bool:
    """
    Offer to email the report.

    The session id travels in the action payload, so tapping a prompt from
    further up the conversation delivers THAT report rather than the newest one.
    Telegram allows 64 bytes of callback data; `email_report:<uuid>` is 49.

    Core sends one action regardless of platform — a platform with buttons
    renders it tappable, one without appends a keyword instruction. Neither
    branch lives here.
    """
    from engines.research_agent.channels.core import constants as k

    result = service.send_prompt(
        adapter,
        contact,
        text=EMAIL_PROMPT,
        action_id=f"{k.ACTION_EMAIL_REPORT}:{session.id}",
        session=session,
    )
    return result is not None


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
    The chat-facing answer, with a one-line record of the work behind it.

    Deliberately the executive summary, not the full report: ~300 words reads
    well on a phone, and the complete text travels in the document. On a
    platform with a smaller cap the summary is trimmed — core does not decide
    that, `capabilities.max_text_chars` does.

    WHY THE WORK LOG IS HERE AND NOT IN SEPARATE PINGS
        The plan was three live progress messages. They are impossible: the
        worker runs ONE task at a time, so `run_research` holds it for the whole
        60–90s and the delivery task cannot interleave. Every "ping" therefore
        arrived seconds before the report — and worse, in the present tense,
        claiming to be searching when searching had finished.

        One past-tense line attached to the answer says the same thing
        truthfully, in one message instead of four.
    """
    body = (report.executive_summary or "").strip() or "(no summary produced)"
    parts = [f"📄 {body}", "\n\n", _work_log(report)]
    return "".join(parts)


def _work_log(report) -> str:
    """
    What the agent actually did, past tense, one line.

    Every figure is read from the finished report, so it can only ever describe
    work that really happened.
    """
    bits = []

    source_count = len(report.sources or [])
    if source_count:
        bits.append(f"🌐 {source_count} sources · credibility scored")

    if report.word_count:
        bits.append(f"📝 {report.word_count} words")

    if report.confidence_score is not None:
        bits.append(f"✅ confidence {round(report.confidence_score * 100)}%")

    return " · ".join(bits) if bits else "Report ready."
