"""
engines/research_agent/agents/base_agent.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BaseAgent — the shared spine every research agent inherits from.

This is a TEMPLATE METHOD pattern:
  - run()      → the LangGraph node function. Same for ALL agents. Handles the
                 boring-but-critical bookkeeping: cancellation, timing, DB logging,
                 state snapshots, telemetry, error handling.
  - execute()  → the ACTUAL BRAIN. Abstract. Each agent overrides this with its
                 own reasoning logic and returns (partial_state, tokens_used).

Why this split?
  Every agent must do the SAME 6 things around its real work:
    1. Skip immediately if the session was cancelled (Risk #36)
    2. Time itself (writes duration_ms to ra_agent_log)
    3. Write a row to ra_agent_log (started → completed/failed)
    4. Snapshot full state after running (ra_state_snapshot, LLMOps demo)
    5. Fold its timing + tokens into the shared telemetry dicts
    6. Never crash the pipeline — catch its own errors, append to state['errors']

  Putting all 6 in BaseAgent means each agent file contains ONLY its reasoning —
  zero boilerplate, zero chance of forgetting to log or check cancellation.

RULES enforced here:
  - cancellation checked as the FIRST thing (Risk #36)
  - all LLM calls route through groq_client retry wrapper (Hard Rule)
  - structlog only, never print()
  - an agent failure is NON-FATAL — it logs, appends to errors, returns safe state
"""

from __future__ import annotations

import time
import structlog
import sentry_sdk
from django.db.models import Max
from django.utils import timezone

from engines.research_agent.constants import SSEEvent
from engines.research_agent.graph.state import ResearchState
from engines.research_agent.models.agent_execution_log import AgentExecutionLog
from engines.research_agent.models.agent_state_snapshot import AgentStateSnapshot

logger = structlog.get_logger(__name__)


class BaseAgent:
    """
    Subclasses MUST set these 4 class attributes and override execute().

    Defaults below are the Groq llama-3.3-70b config. Fast agents
    (Verification, Reflection) override provider="cerebras".
    """

    agent_name: str = "base"
    model_provider: str = "groq"
    model_name: str = "llama-3.3-70b-versatile"
    max_tokens: int = 1024

    # ──────────────────────────────────────────────────────────────────────────
    # PUBLIC: this is what gets registered as the LangGraph node.
    # ──────────────────────────────────────────────────────────────────────────
    def run(self, state: ResearchState) -> dict:
        """
        LangGraph node entry point. Returns a PARTIAL state dict that LangGraph
        merges back into the shared state.

        This method is identical for every agent — the variation lives in execute().
        """
        # ── 1. Cancellation gate (Risk #36) ───────────────────────────────────
        # If the user disconnected, every remaining agent returns instantly.
        # No LLM call, no DB write beyond a 'skipped' log marker.
        if state.get("cancelled", False):
            logger.info(
                "research_agent.agent.skipped_cancelled",
                agent=self.agent_name,
                session_id=state.get("session_id"),
            )
            return {}

        # SSE: this node has started (browser shows it "running").
        self._emit(state, SSEEvent.NODE_STARTED, {"agent": self.agent_name})

        # Set the Langfuse call context so groq_client can attach per-call spans
        # to this session + agent (concurrency-safe; defensive no-op if absent).
        try:
            from engines.research_agent.llmops.langfuse_client import set_call_context

            set_call_context(state.get("session_id"), self.agent_name)
        except Exception:
            pass

        start = time.perf_counter()

        # ── 2. Open the ra_agent_log row (status=started) ─────────────────────
        # update_or_create (not create) so a retry of the SAME agent updates its
        # existing row instead of violating the (session, agent_name) unique key.
        log = self._open_log(state)

        try:
            # ── 3. THE BRAIN — subclass-specific reasoning ────────────────────
            partial, tokens = self.execute(state)
            partial = partial or {}

            duration_ms = int((time.perf_counter() - start) * 1000)

            # ── 4. Fold telemetry into shared state dicts ─────────────────────
            # These dicts are NOT Annotated[operator.add], so we must read the
            # existing value, add our key, and return the merged dict — otherwise
            # we'd wipe out earlier agents' timings/tokens.
            partial = self._merge_telemetry(state, partial, duration_ms, tokens)

            # ── 5. Close the log row (status=completed) ───────────────────────
            if log is not None:
                output_summary = self._summarize_output(partial)
                log.complete(
                    duration_ms=duration_ms,
                    tokens=tokens,
                    output_summary=output_summary,
                )

            # ── 6. Snapshot full state after this node (LLMOps demo) ──────────
            merged_state = {**state, **partial}
            self._capture_snapshot(merged_state)

            # SSE: this node finished (browser marks it complete + shows timing).
            self._emit(
                state,
                SSEEvent.NODE_COMPLETED,
                {
                    "agent": self.agent_name,
                    "duration_ms": duration_ms,
                    "tokens": tokens,
                },
            )

            # Langfuse: record this agent's span (AgentOps trajectory + cost).
            self._trace_agent(
                state, tokens=tokens, duration_ms=duration_ms, success=True
            )

            logger.info(
                "research_agent.agent.completed",
                agent=self.agent_name,
                session_id=state.get("session_id"),
                duration_ms=duration_ms,
                tokens=tokens,
            )
            return partial

        except Exception as exc:
            # An agent failure must NEVER crash the whole pipeline.
            # Log it, mark the row failed, append to state['errors'], and return
            # a safe partial so downstream agents can do best-effort work.
            sentry_sdk.capture_exception(exc)
            logger.error(
                "research_agent.agent.failed",
                agent=self.agent_name,
                session_id=state.get("session_id"),
                error=str(exc),
            )
            if log is not None:
                log.fail(error=str(exc))

            # SSE: node finished (failed) — browser still advances, best-effort.
            self._emit(
                state,
                SSEEvent.NODE_COMPLETED,
                {
                    "agent": self.agent_name,
                    "status": "failed",
                },
            )

            # Langfuse: record the failed span too (visible in the trajectory).
            self._trace_agent(state, tokens=0, duration_ms=0, success=False)

            return {
                "errors": [f"{self.agent_name}: {exc}"],
            }

    # ──────────────────────────────────────────────────────────────────────────
    # ABSTRACT: each agent implements its own reasoning here.
    # ──────────────────────────────────────────────────────────────────────────
    def execute(self, state: ResearchState) -> tuple[dict, int]:
        """
        The agent's actual work. Override in every subclass.

        Returns:
            (partial_state, tokens_used)
              partial_state: dict of ONLY the fields this agent produces
                             e.g. {"sub_queries": [...], "domain": "polity"}
              tokens_used:   total LLM tokens consumed (0 if no LLM call)

        Must NOT touch telemetry/logging/snapshots — BaseAgent.run() owns those.
        """
        raise NotImplementedError(
            f"Agent '{self.agent_name}' must implement execute()."
        )

    # ──────────────────────────────────────────────────────────────────────────
    # PROTECTED HELPERS — shared utilities for subclasses.
    # ──────────────────────────────────────────────────────────────────────────
    def _call_llm(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> tuple[str, int]:
        """
        Single entry point for ALL LLM calls in this engine (Hard Rule).

        Delegates to the global groq_client, which owns retry/backoff, the
        Redis rate-limit check, and (from Phase 7) the Langfuse span wrapper.
        Lazily imported so a missing client never breaks module import.

        Pass response_format={"type": "json_object"} for structured-output agents
        to force valid JSON (eliminates bad-JSON parse failures on gpt-oss).

        Returns:
            (response_text, tokens_used)
        """
        from engines.research_agent.llmops.groq_client import llm_client

        return llm_client.call(
            prompt=prompt,
            system=system,
            provider=self.model_provider,
            model=self.model_name,
            max_tokens=max_tokens or self.max_tokens,
            response_format=response_format,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE — bookkeeping internals.
    # ──────────────────────────────────────────────────────────────────────────
    def _open_log(self, state: ResearchState) -> AgentExecutionLog | None:
        """Create/reset the ra_agent_log row for this agent+session."""
        try:
            log, _ = AgentExecutionLog.objects.update_or_create(
                session_id=state["session_id"],
                agent_name=self.agent_name,
                defaults={
                    "status": AgentExecutionLog.STATUS_STARTED,
                    "started_at": timezone.now(),
                    "completed_at": None,
                    "duration_ms": None,
                    "error": None,
                    "model_provider": self.model_provider,
                    "model_name": self.model_name,
                    "retry_count": state.get("retry_count", 0),
                },
            )
            return log
        except Exception as exc:
            # Logging must never block the agent's real work.
            sentry_sdk.capture_exception(exc)
            logger.warning(
                "research_agent.agent.log_open_failed",
                agent=self.agent_name,
                error=str(exc),
            )
            return None

    def _merge_telemetry(
        self,
        state: ResearchState,
        partial: dict,
        duration_ms: int,
        tokens: int,
    ) -> dict:
        """
        Add this agent's timing + token counts to the shared telemetry dicts
        without clobbering earlier agents' entries.
        """
        agent_timings = {**state.get("agent_timings", {}), self.agent_name: duration_ms}
        tokens_per_agent = {
            **state.get("tokens_per_agent", {}),
            self.agent_name: tokens,
        }

        partial["agent_timings"] = agent_timings
        partial["tokens_per_agent"] = tokens_per_agent
        partial["total_tokens_used"] = state.get("total_tokens_used", 0) + tokens
        return partial

    def _capture_snapshot(self, merged_state: dict) -> None:
        """
        Write the full post-node state to ra_state_snapshot (LLMOps demo).
        Defensive — a snapshot failure must never break the pipeline.
        sequence_num = next slot after the highest seq already recorded for this
        session. Using max+1 (not row count) keeps the ordering strictly
        increasing across re-plan loops — capture() upserts one row per node, so
        row count stays flat on re-runs and would stamp colliding seq values.
        """
        try:
            session_id = merged_state["session_id"]
            last_seq = AgentStateSnapshot.objects.filter(
                session_id=session_id
            ).aggregate(Max("sequence_num"))["sequence_num__max"]
            seq = 0 if last_seq is None else last_seq + 1
            AgentStateSnapshot.capture(
                session_id=session_id,
                node_name=self.agent_name,
                sequence_num=seq,
                state=dict(merged_state),
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.warning(
                "research_agent.agent.snapshot_failed",
                agent=self.agent_name,
                error=str(exc),
            )

    def _summarize_output(self, partial: dict) -> str:
        """
        Build a short human-readable summary of what this agent produced,
        stored in ra_agent_log.output_summary (truncated to 400 chars there).
        Overridable by agents that want a richer summary.
        """
        keys = [
            k
            for k in partial.keys()
            if k not in ("agent_timings", "tokens_per_agent", "total_tokens_used")
        ]
        return f"produced: {', '.join(keys)}" if keys else "no output fields"

    def _emit(self, state: ResearchState, event_type: str, data: dict) -> None:
        """
        Publish a live SSE event for this node (node_started / node_completed).
        Defensive + lazily imported — an SSE failure must NEVER break the agent
        or the pipeline. No-op locally when Redis isn't available.
        """
        try:
            from engines.research_agent.services.sse_service import sse_service

            sse_service.emit(state.get("session_id"), event_type, data)
        except Exception:
            pass

    def _trace_agent(
        self,
        state: ResearchState,
        tokens: int,
        duration_ms: int,
        success: bool,
    ) -> None:
        """
        Record this agent's run as a Langfuse span (AgentOps trajectory + cost).
        Metadata only (no full prompt/response — Risk #52). Fully defensive —
        Langfuse can NEVER break the agent or the pipeline.
        """
        try:
            from engines.research_agent.llmops.langfuse_client import langfuse_client
            from engines.research_agent.llmops.prompt_registry import prompt_registry

            langfuse_client.log_agent_span(
                session_id=state.get("session_id"),
                agent_name=self.agent_name,
                provider=self.model_provider,
                model=self.model_name,
                tokens=tokens,
                duration_ms=duration_ms,
                success=success,
                prompt_version=prompt_registry.get_version(self.agent_name),
            )
        except Exception:
            pass
