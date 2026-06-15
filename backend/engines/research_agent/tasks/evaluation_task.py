"""
engines/research_agent/tasks/evaluation_task.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Background task that scores a completed session's report (DeepEval-style).

Fires ONLY after the session is completed (the orchestrator calls
`evaluate_session(session_id)` after `workflow_completed`) — so the user already
has their report; scoring never blocks them (Risk #30).

django-background-tasks (Celery was removed). The worker (`process_tasks`)
executes it. Registered in apps.py ready() so the worker knows about it.

Writes the 4 scores to ra_evaluation, then computes the composite confidence and
pushes it onto ra_report.confidence_score (the user's "Research Confidence %").
"""

from __future__ import annotations

import time

import structlog
import sentry_sdk
from background_task import background

logger = structlog.get_logger(__name__)


@background(schedule=0)
def evaluate_session(session_id: str) -> None:
    """Enqueued by the orchestrator; executed by the background-tasks worker."""
    from engines.research_agent.models.research_session import ResearchSession
    from engines.research_agent.models.evaluation_result import EvaluationResult
    from engines.research_agent.evaluation.deepeval_runner import evaluation_runner

    logger.info("research_agent.eval_task.started", session_id=session_id)

    try:
        session = (
            ResearchSession.objects.filter(id=session_id)
            .select_related("report")
            .first()
        )
        if session is None:
            return
        report = getattr(session, "report", None)
        if report is None or not (report.full_report or "").strip():
            logger.info("research_agent.eval_task.no_report", session_id=session_id)
            return

        t0 = time.perf_counter()
        scores = evaluation_runner.evaluate(
            query=session.query,
            report=report.full_report,
            sources=report.sources or [],
        )
        duration_ms = int((time.perf_counter() - t0) * 1000)

        evaluation, _ = EvaluationResult.objects.update_or_create(
            session=session,
            defaults={
                "faithfulness_score": scores["faithfulness"],
                "relevance_score": scores["relevance"],
                "hallucination_score": scores["hallucination"],
                "completeness_score": scores["completeness"],
                "metrics_detail": scores.get("detail", {}),
                "evaluation_duration_ms": duration_ms,
            },
        )
        # Computes the weighted composite AND writes it to ra_report.confidence_score.
        composite = evaluation.compute_and_save_composite()

        # Back-fill the score into the Redis cache so FUTURE identical-query cache
        # hits serve a complete report (the cached blob was stored with
        # confidence_score=None before DeepEval finished). Defensive — a cache
        # miss/Redis-down just leaves the cached entry's score null; harmless.
        if composite is not None:
            try:
                from engines.research_agent.services.cache_service import cache_service

                cache_service.patch_confidence(session.query_hash, composite)
            except Exception:
                pass

        logger.info(
            "research_agent.eval_task.completed",
            session_id=session_id,
            composite=composite,
            duration_ms=duration_ms,
        )
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logger.error(
            "research_agent.eval_task.failed", session_id=session_id, error=str(exc)
        )
