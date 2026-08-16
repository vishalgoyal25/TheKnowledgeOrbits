"""
engines/research_agent/channels/core/email_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Emailing a finished report, with both file formats attached.

ONE SOURCE OF TRUTH
    `export_service.export_markdown()` already composes the whole report —
    title, confidence, executive summary, full text, numbered sources — for the
    PDF. This renders THAT markdown to HTML for the email body, so the email,
    the PDF and the website's download can never drift apart.

WHY DIRECT CALLS, NOT THE PUBLIC URL
    The chat document goes through the export URL because a provider has to
    fetch it or receive it as an upload. Email attachments are assembled inside
    this process, so a round trip through our own public hostname would buy
    nothing.

DEGRADATION
    PDF needs WeasyPrint, which is production-only. When it is unavailable the
    email still goes out with the Markdown attachment and the full HTML body —
    the same "never nothing" rule the chat document follows.

⚠️ Dev sends to the console unless USE_REAL_EMAIL_IN_DEV=True.
"""

from __future__ import annotations

import structlog
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = structlog.get_logger(__name__)

_STYLE = """
  body { font-family: -apple-system, 'Segoe UI', Arial, sans-serif;
         line-height: 1.6; color: #1a1a1a; max-width: 720px; margin: 0 auto;
         padding: 24px 16px; }
  h1 { font-size: 22px; border-bottom: 2px solid #2563eb; padding-bottom: 8px; }
  h2 { font-size: 17px; color: #1e3a8a; margin-top: 28px; }
  a  { color: #2563eb; }
  em { color: #555; }
  .footer { margin-top: 36px; padding-top: 16px; border-top: 1px solid #e5e7eb;
            font-size: 13px; color: #666; }
"""


class EmailDeliveryError(Exception):
    """Sending failed. The caller tells the user; nothing is retried silently."""


def send_report(session, address: str) -> str:
    """
    Email one report. Returns the export format actually attached.

    Raises EmailDeliveryError on failure so the caller can say so in chat —
    silently failing here would leave someone waiting for mail that never comes.
    """
    from engines.research_agent.services.export_service import (
        ExportError,
        export_service,
    )

    session_id = str(session.id)

    try:
        md_name, md_text = export_service.export_markdown(session_id)
    except ExportError as exc:
        # No report to send at all — nothing further is worth attempting.
        raise EmailDeliveryError(f"export failed: {exc}") from exc

    message = EmailMultiAlternatives(
        subject=_subject(session),
        body=md_text,  # plain-text alternative: the markdown itself
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=[address],
    )
    message.attach_alternative(_html_body(session, md_text), "text/html")
    message.attach(md_name, md_text.encode("utf-8"), "text/markdown")

    export_format = "md"
    try:
        pdf_name, pdf_bytes = export_service.export_pdf(session_id)
        message.attach(pdf_name, pdf_bytes, "application/pdf")
        export_format = "pdf+md"
    except ExportError:
        # Expected on any machine without WeasyPrint. The Markdown attachment
        # and the HTML body still carry the whole report.
        logger.info("channel.email.pdf_unavailable", session_id=session_id)

    try:
        message.send(fail_silently=False)
    except Exception as exc:
        raise EmailDeliveryError(str(exc)) from exc

    logger.info(
        "channel.email.sent",
        session_id=session_id,
        export_format=export_format,
        attachments=len(message.attachments),
    )
    return export_format


def _subject(session) -> str:
    """The question itself — recognisable in an inbox, and searchable."""
    query = (session.query or "Research report").strip()
    return query if len(query) <= 120 else query[:117].rstrip() + "…"


def _html_body(session, md_text: str) -> str:
    """
    The report as HTML.

    Rendered from the same markdown the PDF is built from, using the same
    library `export_service` uses. If markdown_it is missing we fall back to
    preformatted text rather than sending an empty email.
    """
    try:
        from markdown_it import MarkdownIt

        rendered = MarkdownIt().render(md_text)
    except Exception:
        escaped = md_text.replace("<", "&lt;").replace(">", "&gt;")
        rendered = f"<pre>{escaped}</pre>"

    site = getattr(settings, "FRONTEND_URL", "") or ""
    footer = (
        f'<p class="footer">Researched by '
        f'<a href="{site}">TheKnowledgeOrbits</a> · '
        f"the full report is attached as PDF and Markdown.</p>"
        if site
        else '<p class="footer">The full report is attached as PDF and Markdown.</p>'
    )

    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{_STYLE}</style></head><body>{rendered}{footer}</body></html>"
    )
