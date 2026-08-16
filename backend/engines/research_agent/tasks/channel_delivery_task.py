"""
engines/research_agent/tasks/channel_delivery_task.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Watching a run and delivering the result to a chat.

WHY POLLING, AND WHY IT MUST NOT BLOCK
    The obvious design — subscribe to the session's Redis channel and wait — is
    a DEADLOCK here. `process_tasks` runs ONE task at a time: a subscriber
    enqueued alongside `run_research` would occupy the worker while waiting for
    events that the research task, still queued behind it, cannot produce.

    So this task never waits. It checks, sends whatever is due, and RE-ENQUEUES
    itself a few seconds later. The worker is free between checks, and the
    research task interleaves normally.

    Progress comes from `AgentExecutionLog`, which the agent writes as it goes —
    no pub/sub, and `sse_service.py` (frozen) is untouched.

⚠️ Registered in `ResearchAgentConfig.ready()`. A @background task the worker
never imported is enqueued successfully and then never runs — silently.
"""

from __future__ import annotations

import sentry_sdk
import structlog
from background_task import background

logger = structlog.get_logger(__name__)

# How often to look. Short enough that a ping lands close to the moment it is
# true, long enough that a 90-second run costs ~18 cheap queries rather than
# hundreds.
POLL_SECONDS = 5

# Give up after roughly 4 minutes. The workflow is 40–90s; anything past this
# is a stuck or crashed run, and an honest apology beats infinite silence.
MAX_ATTEMPTS = 48


@background(schedule=POLL_SECONDS)
def deliver_when_ready(
    session_id: str, attempt: int = 0, instant: bool = False
) -> None:
    """
    One poll: send any new progress, then finish or re-schedule.

    `instant=True` is used when reusing an already-finished session for a repeat
    question. There is no work to narrate, so progress pings are skipped and the
    report goes straight out.

    Never raises. A delivery failure must not mark the task failed and retry the
    whole thing — that would re-send messages the user already has.
    """
    from engines.research_agent.channels.core import delivery, progress, registry
    from engines.research_agent.constants import SessionChannel, SessionStatus
    from engines.research_agent.models.research_session import ResearchSession

    try:
        session = ResearchSession.objects.filter(pk=session_id).first()
        if session is None:
            logger.error("channel.delivery.session_missing", session_id=session_id)
            return

        if session.channel == SessionChannel.WEB:
            # Should be unreachable — web never enqueues this. Guard anyway, so
            # a stray call can never message someone.
            return

        adapter = registry.get(session.channel)
        if adapter is None or not adapter.is_operational():
            logger.warning(
                "channel.delivery.adapter_unavailable",
                session_id=session_id,
                channel=session.channel,
            )
            return

        contact = delivery.contact_for_session(session)
        if contact is None:
            logger.error("channel.delivery.no_contact", session_id=session_id)
            return

        # ── Terminal states ──────────────────────────────────────────────────
        if session.status == SessionStatus.COMPLETED:
            if not instant:
                delivery.send_progress(adapter, contact, session)

            # The document only goes out if there was something to summarise —
            # otherwise a run that produced no report would still attach a file.
            if delivery.send_summary(adapter, contact, session):
                delivery.send_document(adapter, contact, session)

            # T6 adds the email prompt here.
            progress.clear(session_id)
            logger.info(
                "channel.delivery.done",
                session_id=session_id,
                channel=session.channel,
                polls=attempt + 1,
                instant=instant,
            )
            return

        if session.status in (SessionStatus.FAILED, SessionStatus.CANCELLED):
            delivery.send_failure(adapter, contact, session, session.status)
            progress.clear(session_id)
            return

        # ── Still running ────────────────────────────────────────────────────
        delivery.send_progress(adapter, contact, session)

        if attempt + 1 >= MAX_ATTEMPTS:
            delivery.send_failure(adapter, contact, session, "timeout")
            progress.clear(session_id)
            logger.error(
                "channel.delivery.gave_up", session_id=session_id, polls=attempt + 1
            )
            return

        # Check again shortly. Re-enqueueing rather than sleeping is what keeps
        # the single worker available for the research task itself.
        deliver_when_ready(session_id, attempt + 1, instant)

    except Exception as exc:
        logger.error(
            "channel.delivery.poll_failed", session_id=session_id, error=str(exc)
        )
        sentry_sdk.capture_exception(exc)
