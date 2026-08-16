"""
engines/research_agent/channels/core/progress.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Turning workflow progress into human sentences.

WHERE PROGRESS COMES FROM
    `AgentExecutionLog` — the agent already writes one row per node as it runs.
    Reading those rows means we need NO Redis pub/sub tap, and `sse_service.py`
    (frozen) is untouched. The browser keeps its live SSE stream; chat gets the
    same information from the database the agent was already filling in.

WHY ONLY THREE PINGS
    A 40–90s silence reads as "broken". Three well-timed messages make the wait
    feel like work happening. Eight would make the bot feel like a spammer, and
    on a metered provider each one costs money.

IDEMPOTENCE
    The delivery task polls repeatedly, so "have we already said this?" must
    survive across runs. A Redis set per session records which milestones were
    sent. If Redis is unavailable we send NOTHING rather than risk repeating
    ourselves — a missing ping is a small disappointment, a duplicated one looks
    broken.
"""

from __future__ import annotations

import structlog

from engines.research_agent.constants import AgentName

logger = structlog.get_logger(__name__)

# Milestones, in workflow order. Keyed on the agent node whose COMPLETION marks
# the moment. Nodes not listed here pass silently — supervisor, verification,
# summary_generator and reflection are internal steps a user does not need
# narrated.
MILESTONES: tuple[tuple[str, str], ...] = (
    (AgentName.SEARCH, "🌐 Searching across sources…"),
    (AgentName.RESEARCH, "📚 Reading and credibility-scoring what I found…"),
    (AgentName.REPORT_GENERATOR, "✍️ Writing your report…"),
)

_SENT_KEY = "channel:progress:{session_id}"
_SENT_TTL = 3600  # an hour outlives any run; the key is disposable


def pending_messages(session_id: str) -> list[str]:
    """
    Milestones reached but not yet announced, in order.

    Marks them sent BEFORE returning: the caller is about to send them, and a
    crash between marking and sending costs one ping, whereas the reverse order
    could repeat a ping on every poll.
    """
    reached = _reached_nodes(session_id)
    if not reached:
        return []

    conn = _redis()
    if conn is None:
        # Fail CLOSED for progress. Without a memory of what was sent, polling
        # would re-send the same ping every few seconds.
        logger.warning(
            "channel.progress.redis_unavailable_skipping", session_id=session_id
        )
        return []

    key = _SENT_KEY.format(session_id=session_id)
    messages: list[str] = []

    try:
        for node, text in MILESTONES:
            if node not in reached:
                continue
            # sadd returns 1 only the first time this node is added — atomic,
            # so two workers polling at once cannot both claim the same ping.
            if conn.sadd(key, node) == 1:
                messages.append(text)
        if messages:
            conn.expire(key, _SENT_TTL)
    except Exception as exc:
        logger.warning(
            "channel.progress.redis_error", session_id=session_id, error=str(exc)
        )
        return []

    return messages


def clear(session_id: str) -> None:
    """Drop the marker set once a run has finished. Best-effort."""
    conn = _redis()
    if conn is None:
        return
    try:
        conn.delete(_SENT_KEY.format(session_id=session_id))
    except Exception:
        pass


def _reached_nodes(session_id: str) -> set[str]:
    """
    Which agent nodes have completed so far.

    Reads the ops table the agent writes anyway — no extra instrumentation, and
    nothing for the pipeline to emit on our behalf.
    """
    from engines.research_agent.constants import SessionStatus
    from engines.research_agent.models.agent_execution_log import AgentExecutionLog

    return set(
        AgentExecutionLog.objects.filter(
            session_id=session_id, status=SessionStatus.COMPLETED
        ).values_list("agent_name", flat=True)
    )


def _redis():
    """Same connection helper as middleware/rate_limiter.py."""
    try:
        from django_redis import get_redis_connection

        return get_redis_connection("default")
    except Exception:
        return None
