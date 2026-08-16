"""
engines/research_agent/tasks/channel_email_task.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sending a report by email, off the message-handling path.

Rendering a PDF and talking to an SMTP relay both take seconds, and neither
belongs in the code path answering a chat message. The user is told "sending it
now" immediately; this does the work and reports back if it fails.

Every attempt is recorded in `ra_report_delivery` — which is why that is a table
and not a column on the session. One report can be emailed twice, to two
addresses, with one of them failing, and "I never got it" needs an answer.

⚠️ Registered in `ResearchAgentConfig.ready()`. A @background task the worker
never imported is enqueued successfully and then never runs — silently.
"""

from __future__ import annotations

import sentry_sdk
import structlog
from background_task import background

logger = structlog.get_logger(__name__)

SENT_REPLY = "📧 Sent to {address} — check your inbox (and spam, just in case)."

FAILED_REPLY = (
    "I couldn't send that email. Please double-check the address and try again."
)


@background(schedule=0)
def send_report_email(session_id: str, address: str, contact_id: str) -> None:
    """
    Email one report and tell the user what happened.

    Never raises: a failed send must not mark the task failed and retry, because
    a retry could deliver the same report twice while the user has already been
    told it failed.
    """
    from engines.research_agent.channels.core import email_service, registry
    from engines.research_agent.channels.core import service as channel_service
    from engines.research_agent.channels.core.constants import (
        DeliveryChannel,
        DeliveryStatus,
    )
    from engines.research_agent.channels.core.models import (
        ChannelContact,
        ReportDelivery,
    )
    from engines.research_agent.models.research_session import ResearchSession

    session = ResearchSession.objects.filter(pk=session_id).first()
    contact = ChannelContact.objects.filter(pk=contact_id).first()

    if session is None or contact is None:
        logger.error(
            "channel.email.context_missing",
            session_id=session_id,
            contact_id=contact_id,
        )
        return

    adapter = registry.get(contact.channel)

    delivery_row = ReportDelivery.objects.create(
        session=session,
        contact=contact,
        channel=DeliveryChannel.EMAIL,
        destination=address,
        export_format="pdf",  # corrected below to what actually attached
        status=DeliveryStatus.PENDING,
    )

    try:
        export_format = email_service.send_report(session, address)
        delivery_row.export_format = export_format
        delivery_row.save(update_fields=["export_format"])
        delivery_row.mark_sent()

        if adapter is not None:
            channel_service.send_text(
                adapter,
                contact,
                SENT_REPLY.format(address=address),
                session=session,
            )

    except Exception as exc:
        # ⚠️ The address is PII — it belongs in the delivery row (our own DB),
        # never in a log line that reaches Sentry.
        logger.error(
            "channel.email.failed",
            session_id=session_id,
            channel=contact.channel,
            external_hash=contact.external_hash,
            error=str(exc)[:300],
        )
        sentry_sdk.capture_exception(exc)
        delivery_row.mark_failed(str(exc)[:500])

        if adapter is not None:
            channel_service.send_text(adapter, contact, FAILED_REPLY, session=session)
