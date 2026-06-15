"""
engines/research_agent/agents/supervisor_agent.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SupervisorAgent — the gatekeeper. First node in the graph.

It does NOT do research. Its only job is to decide:
  "Is this query safe and sane enough to spend LLM budget on?"

Responsibilities:
  1. Validate the query — not empty, within length bounds.
  2. Cheap prompt-injection screen — block obvious jailbreak attempts
     BEFORE any LLM call is made (Risk #39). The comprehensive guardrails
     middleware arrives in Phase 6; this is the fast first line of defense.
  3. Open the Langfuse trace for the whole session (Phase 7 hook).

No LLM call → tokens = 0. This node is pure, fast validation.

If the query is rejected, the Supervisor sets cancelled=True. Because every
agent checks cancelled first (BaseAgent.run step 1), this cleanly short-circuits
the ENTIRE downstream pipeline — no plan, no search, no wasted LLM budget.
"""

from __future__ import annotations

import structlog

from engines.research_agent.agents.base_agent import BaseAgent
from engines.research_agent.constants import AgentName
from engines.research_agent.graph.state import ResearchState
from engines.research_agent.middleware.guardrails import guardrails

logger = structlog.get_logger(__name__)

# Query validation bounds (named, not magic numbers buried in code).
MIN_QUERY_LENGTH = 5  # "hi" is not a research question
MAX_QUERY_LENGTH = 1000  # guard against prompt-stuffing / cost blowup


class SupervisorAgent(BaseAgent):
    agent_name = AgentName.SUPERVISOR
    # Supervisor makes no LLM call, but we keep provider metadata consistent
    # so the ra_agent_log row has sensible model_provider/model_name values.
    model_provider = "groq"
    model_name = "llama-3.3-70b-versatile"

    def execute(self, state: ResearchState) -> tuple[dict, int]:
        query = (state.get("query") or "").strip()

        # ── Validate length ───────────────────────────────────────────────────
        rejection = self._validate(query)
        if rejection is not None:
            logger.warning(
                "research_agent.supervisor.rejected",
                session_id=state.get("session_id"),
                reason=rejection,
            )
            # Halt the whole pipeline gracefully: cancelled=True makes every
            # downstream agent skip itself in BaseAgent.run step 1.
            return (
                {
                    "cancelled": True,
                    "errors": [f"supervisor_rejected: {rejection}"],
                },
                0,
            )

        # ── Open Langfuse trace (Phase 7 hook) ────────────────────────────────
        trace_id = self._open_trace(state)

        logger.info(
            "research_agent.supervisor.accepted",
            session_id=state.get("session_id"),
            query_len=len(query),
        )

        partial: dict = {}
        if trace_id is not None:
            partial["langfuse_trace_id"] = trace_id

        return partial, 0

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────────────────────────────────
    def _validate(self, query: str) -> str | None:
        """
        Returns a rejection reason string, or None if the query is acceptable.
        """
        if not query:
            return "empty_query"
        if len(query) < MIN_QUERY_LENGTH:
            return "query_too_short"
        if len(query) > MAX_QUERY_LENGTH:
            return "query_too_long"

        # Comprehensive prompt-injection screen (Phase 6 guardrails middleware).
        allowed, reason = guardrails.check_input(query)
        if not allowed:
            return reason

        return None

    def _open_trace(self, state: ResearchState) -> str | None:
        """
        Start the Langfuse trace for this session (trace_id derived from
        session_id) and return its trace_id → stored on ResearchSession via
        state['langfuse_trace_id']. Returns None if Langfuse is disabled.
        Fully defensive — never breaks the pipeline.
        """
        try:
            from engines.research_agent.llmops.langfuse_client import langfuse_client

            return langfuse_client.start_trace(
                session_id=state.get("session_id"),
                query=state.get("query") or "",
                user_id=state.get("user_id"),
            )
        except Exception:
            return None
