"""
engines/research_agent/tasks/channel_delivery_task.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Watching a run and delivering the result to a chat.

WHY POLLING, AND WHY IT MUST NOT BLOCK
    The obvious design — subscribe to the session's Redis channel and wait — is
    a DEADLOCK here. `process_tasks` runs ONE task at a time: a subscriber
    enqueued alongside `run_research` would occupy the worker while waiting for
    events that the research task, still queued behind it, cannot produce.

    So this task never waits. It checks, and if the run is not finished it
    RE-ENQUEUES itself a few seconds later, leaving the worker free in between.

⚠️ THIS STILL DOES NOT GIVE LIVE PROGRESS
    With ONE worker, `run_research` occupies it for the entire 60–90s, so this
    task cannot actually run mid-flight — its first real execution is after the
    research has finished. That is why there are no progress pings: they would
    all arrive at the end, in the present tense, describing work already done.

    The polling loop still earns its place — it is what handles a run that
    crashes, hangs or is cancelled, and it is what makes live progress possible
    the day a second worker exists on its own queue.

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

# Extra polls to wait for the confidence score once the report itself is ready.
#
# The score is NOT produced by the workflow. The orchestrator writes the report
# with confidence_score=None, marks the session completed, and only then
# enqueues `evaluate_session` — a separate task that runs DeepEval and fills it
# in afterwards.
#
# Those two tasks race, and we lose: `background_task` picks the earliest
# `run_at`, and this task was queued when the question arrived — a minute before
# the evaluation was queued. So without waiting we always deliver first and the
# report reads "confidence: pending", then the score appears seconds later,
# visible in a re-delivery or the emailed copy but not in the original reply.
#
# Measured evaluation time: ~3.8s average, 5.6s worst case. Six polls is 30s —
# roughly five times the worst case, so the wait is invisible in practice while
# still guaranteeing delivery if DeepEval fails or is disabled entirely.
SCORE_WAIT_POLLS = 6


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
    from engines.research_agent.channels.core import delivery, registry
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
            # Hold briefly for the confidence score. Delivering without it is
            # what made the first reply say "pending" while the emailed copy
            # showed the real number — the same report, contradicting itself.
            if _awaiting_score(session) and attempt < SCORE_WAIT_POLLS:
                logger.debug(
                    "channel.delivery.waiting_for_score",
                    session_id=session_id,
                    poll=attempt + 1,
                )
                deliver_when_ready(session_id, attempt + 1, instant)
                return

            # The document and prompt only go out if there was something to
            # summarise — otherwise a run that produced no report would still
            # attach a file and offer to email it.
            if delivery.send_summary(adapter, contact, session):
                delivery.send_document(adapter, contact, session)
                delivery.send_email_prompt(adapter, contact, session)

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
            return

        # ── Still running ────────────────────────────────────────────────────
        if attempt + 1 >= MAX_ATTEMPTS:
            delivery.send_failure(adapter, contact, session, "timeout")
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


def _awaiting_score(session) -> bool:
    """
    True when the report exists but DeepEval has not scored it yet.

    False when there is no report at all — that is a different failure, handled
    by `send_summary`, and waiting for a score that will never come would only
    delay telling the user something went wrong.
    """
    from engines.research_agent.models.research_report import ResearchReport

    report = (
        ResearchReport.objects.filter(session=session).only("confidence_score").first()
    )
    return report is not None and report.confidence_score is None
