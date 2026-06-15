"""
engines/research_agent/services/orchestrator.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ResearchOrchestrator — the conductor.

Runs ONE research session end-to-end. Called by the Celery task
(tasks/research_task.py), NEVER in the Django request thread — the workflow
takes 30-90s and Render kills HTTP requests at 30s (Risk #1).

Responsibilities (coordination only — it does NOT reason; the agents do):
  1. Mark the session RUNNING.
  2. Build the initial ResearchState and invoke the compiled LangGraph.
  3. Emit lifecycle SSE events (workflow_started / completed / failed / cancelled)
     via sse_service → Redis pub/sub → the browser's SSE stream.
     (Per-node events are emitted by BaseAgent; report tokens by ReportGenerator.)
  4. Persist the final ResearchReport to the DB.
  5. Mark the session COMPLETED/FAILED and tear down the SSE channel.
  6. Trigger the background DeepEval task AFTER workflow_completed (never blocks
     the user) — wired in Phase 9.

It owns the session LIFECYCLE; the graph owns the WORK.
"""

from __future__ import annotations

import structlog
import sentry_sdk

from engines.research_agent.constants import SSEEvent
from engines.research_agent.graph.graph import get_compiled_graph
from engines.research_agent.graph.state import make_initial_state
from engines.research_agent.models.research_session import ResearchSession
from engines.research_agent.models.research_report import ResearchReport
from engines.research_agent.services.sse_service import sse_service

logger = structlog.get_logger(__name__)


class ResearchOrchestrator:
    """Stateless coordinator — safe to instantiate per task or use the singleton."""

    def run(self, session_id: str) -> None:
        """
        Execute the full workflow for one session.

        This method NEVER raises to the caller — any failure is captured, the
        session is marked FAILED, a workflow_failed SSE event is emitted, and
        the SSE channel is closed. The Celery task stays green.
        """
        try:
            session = ResearchSession.objects.get(id=session_id)
        except ResearchSession.DoesNotExist:
            logger.error(
                "research_agent.orchestrator.session_missing", session_id=session_id
            )
            return

        # If the user already cancelled before the worker picked it up, bail.
        if sse_service.is_cancelled(session_id) or session.cancelled:
            session.mark_cancelled()
            sse_service.emit(
                session_id,
                SSEEvent.WORKFLOW_CANCELLED,
                {"reason": "cancelled_before_start"},
            )
            sse_service.close(session_id)
            return

        try:
            session.mark_running()
            sse_service.emit(
                session_id,
                SSEEvent.WORKFLOW_STARTED,
                {"query": session.query, "status": "running"},
            )

            final_state = self._invoke_graph(session)

            # The graph may have been cancelled mid-flight (browser disconnect).
            if final_state.get("cancelled"):
                session.mark_cancelled()
                sse_service.emit(
                    session_id,
                    SSEEvent.WORKFLOW_CANCELLED,
                    {"reason": "cancelled_mid_run"},
                )
                return

            self._save_report(session, final_state)

            total_tokens = final_state.get("total_tokens_used", 0)
            session.mark_completed(total_tokens=total_tokens)

            # Cache the report for identical future queries + record user memory.
            self._cache_and_remember(session, final_state)

            sse_service.emit(
                session_id,
                SSEEvent.WORKFLOW_COMPLETED,
                {
                    "word_count": final_state.get("report_word_count", 0),
                    "total_tokens": total_tokens,
                    "reflection_score": final_state.get("reflection_score"),
                },
            )

            logger.info(
                "research_agent.orchestrator.completed",
                session_id=session_id,
                total_tokens=total_tokens,
            )

            self._trigger_evaluation(session_id)

        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error(
                "research_agent.orchestrator.failed",
                session_id=session_id,
                error=str(exc),
            )
            session.mark_failed(str(exc))
            sse_service.emit(
                session_id, SSEEvent.WORKFLOW_FAILED, {"error": "internal_error"}
            )

        finally:
            # Flush Langfuse ONCE at the end (Risk #16) — never per-call.
            self._flush_langfuse()
            # Always close the SSE channel so the browser's stream ends cleanly.
            sse_service.close(session_id)

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────────────────────────────────
    def _invoke_graph(self, session: ResearchSession) -> dict:
        """
        Build the initial state and run the compiled LangGraph. thread_id =
        session_id ties this run to its checkpoints (resume on crash).
        """
        graph = get_compiled_graph()
        initial_state = make_initial_state(
            session_id=str(session.id),
            query=session.query,
            user_id=str(session.user_id) if session.user_id else None,
        )
        config = {"configurable": {"thread_id": str(session.id)}}
        return graph.invoke(initial_state, config=config)

    def _save_report(self, session: ResearchSession, state: dict) -> None:
        """
        Persist the final output to ra_report (upsert — a re-run of the same
        session updates its existing report rather than duplicating).
        confidence_score is left null; DeepEval fills it later (Phase 9).
        """
        # Output guardrails (Phase 6) — strip dangerous HTML from LLM markdown
        # before it's persisted/served (defense-in-depth behind frontend sanitize).
        from engines.research_agent.middleware.guardrails import guardrails

        summary = guardrails.sanitize_output(state.get("executive_summary") or "")
        report = guardrails.sanitize_output(state.get("final_report") or "")

        ResearchReport.objects.update_or_create(
            session=session,
            defaults={
                "executive_summary": summary,
                "full_report": report,
                "sources": self._extract_sources(state),
                "word_count": state.get("report_word_count", 0),
            },
        )

    @staticmethod
    def _extract_sources(state: dict) -> list[dict]:
        """Trim raw search results to the citation-relevant fields for the report."""
        sources = state.get("raw_search_results") or []
        return [
            {
                "url": s.get("url", ""),
                "title": s.get("title", ""),
                "credibility_score": s.get("credibility_score"),
            }
            for s in sources
            if s.get("url")
        ]

    def _cache_and_remember(self, session: ResearchSession, state: dict) -> None:
        """
        Phase 8: cache the finished report (so identical future queries return
        instantly) and record the user's domain interest in long-term memory.
        Both are defensive — a cache/memory failure never affects the result.
        Only caches a report with real content.
        """
        report_text = (state.get("final_report") or "").strip()
        if report_text:
            try:
                from engines.research_agent.services.cache_service import cache_service

                cache_service.set(
                    session.query_hash,
                    {
                        "executive_summary": state.get("executive_summary") or "",
                        "full_report": report_text,
                        "sources": self._extract_sources(state),
                        "word_count": state.get("report_word_count", 0),
                        # DeepEval runs ~seconds later — store the key now (None) so a
                        # cache hit serializes `confidence_score: null` (not a missing
                        # key → NaN on the client). The evaluation task back-fills the
                        # real score via cache_service.patch_confidence() once scored.
                        "confidence_score": None,
                    },
                )
            except Exception:
                pass

        if session.user_id:
            try:
                from engines.research_agent.services.memory_service import (
                    memory_service,
                )

                memory_service.record_query(str(session.user_id), state.get("domain"))
            except Exception:
                pass

    def _flush_langfuse(self) -> None:
        """Flush queued Langfuse events at session end. Defensive — never raises."""
        try:
            from engines.research_agent.llmops.langfuse_client import langfuse_client

            langfuse_client.flush()
        except Exception:
            pass

    def _trigger_evaluation(self, session_id: str) -> None:
        """
        Phase 9 hook — fire the background DeepEval task AFTER the user already
        has the report. Wrapped defensively so a missing task never affects the
        completed workflow.
        """
        try:
            from engines.research_agent.tasks.evaluation_task import evaluate_session

            evaluate_session(session_id)  # background-tasks: calling enqueues it
        except Exception:
            # evaluation_task not implemented until Phase 9 — non-fatal.
            logger.debug(
                "research_agent.orchestrator.eval_skipped", session_id=session_id
            )


# Module-level singleton — imported by the Celery task.
research_orchestrator = ResearchOrchestrator()
