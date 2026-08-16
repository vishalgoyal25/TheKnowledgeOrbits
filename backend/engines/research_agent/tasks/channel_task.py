"""
engines/research_agent/tasks/channel_task.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Background handling of one inbound channel message.

WHY THE WEBHOOK DOES NOT DO THIS INLINE
    The webhook must acknowledge in milliseconds. Providers retry anything slow
    or non-2xx, and from T3 this path creates a ResearchSession and runs the
    8-node workflow — 40 to 90 seconds. Even today's echo makes an outbound HTTP
    call, which has no business inside a webhook request.

    So the webhook verifies, parses, enqueues and returns 200. Everything real
    happens here, in `python manage.py process_tasks`.

⚠️ If the worker is not running, messages queue silently and the bot never
replies — with no error anywhere. That is the single most likely way to lose an
hour on this feature. THREE terminals: runserver · process_tasks · ngrok.

The payload is a plain dict because django-background-tasks serialises task
arguments to JSON; a dataclass cannot survive that trip.
"""

from __future__ import annotations

import sentry_sdk
import structlog
from background_task import background

logger = structlog.get_logger(__name__)


@background(schedule=0)
def handle_channel_update(channel: str, inbound_data: dict) -> None:
    """
    Act on one already-verified, already-parsed inbound message.

    Imports are deferred to call time so the module stays cheap for Django
    startup and for management commands that never touch channels.

    Exceptions are captured and swallowed: the provider has already been given
    a 200, so raising here would only mark the task failed without informing
    anyone. Sentry is the notification path.
    """
    from engines.research_agent.channels.core import registry, service
    from engines.research_agent.channels.core.adapter import InboundMessage

    adapter = registry.get(channel)
    if adapter is None:
        # The channel was disabled or removed between the webhook accepting the
        # message and the worker picking it up. Nothing to do.
        logger.error("channel.task.no_adapter", channel=channel)
        return

    try:
        inbound = InboundMessage(**inbound_data)
    except TypeError as exc:
        # A shape mismatch between what the webhook enqueued and what the
        # dataclass expects — a coding error, not a user error.
        logger.error("channel.task.bad_payload", channel=channel, error=str(exc))
        sentry_sdk.capture_exception(exc)
        return

    try:
        outcome = service.handle_inbound(adapter, inbound)
        logger.info(
            "channel.task.handled",
            channel=channel,
            provider_message_id=inbound.provider_message_id,
            outcome=outcome,
        )
    except Exception as exc:
        logger.error(
            "channel.task.failed",
            channel=channel,
            provider_message_id=inbound.provider_message_id,
            error=str(exc),
        )
        sentry_sdk.capture_exception(exc)
