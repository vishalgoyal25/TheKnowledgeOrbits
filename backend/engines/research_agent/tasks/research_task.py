"""
engines/research_agent/tasks/research_task.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Background task that runs the full LangGraph research workflow OFF the request
thread (Hard Rule, Risk #1 — Render kills HTTP requests at 30s; the workflow
needs 30-90s).

This project uses django-background-tasks (Celery was removed — see
core/__init__.py), matching every other engine's task pattern. The view calls
`run_research(session_id)` which ENQUEUES the job and returns instantly; the
`python manage.py process_tasks` worker executes it and delegates to the
orchestrator, which runs the graph and streams progress via SSE.
"""

from __future__ import annotations

import structlog
import sentry_sdk
from background_task import background

logger = structlog.get_logger(__name__)


@background(schedule=0)
def run_research(session_id: str) -> None:
    """
    Enqueued by query_view; executed by the background-tasks worker.

    Imports are deferred to call time so enqueuing (in the web process) never
    builds the compiled graph / heavy deps.
    """
    from engines.research_agent.services.orchestrator import research_orchestrator
    from engines.research_agent.services.sse_service import sse_service

    logger.info("research_agent.task.started", session_id=session_id)

    try:
        # The orchestrator owns the whole lifecycle (status, SSE, persistence)
        # and never raises — but this is the final safety net.
        research_orchestrator.run(session_id)
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logger.error(
            "research_agent.task.failed", session_id=session_id, error=str(exc)
        )
        sse_service.close(session_id)
