"""
engines/research_agent/tests/test_graph.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tests for the LangGraph state + conditional routing.

  - make_initial_state()       — every TypedDict key present + correct defaults
  - route_after_verification() — pass / retry-within-budget / exhausted / cancel
  - route_after_reflection()   — pass / re-plan-within-budget / exhausted / cancel

The routers are the ONLY decision points in the whole graph, so they are the
highest-value thing to pin down. Pure functions — no DB, no LLM.
"""

from __future__ import annotations

from langgraph.graph import END

from engines.research_agent.constants import (
    MAX_REFLECTION_PASSES,
    MAX_VERIFICATION_RETRIES,
)
from engines.research_agent.graph.router import (
    REFLECTION_THRESHOLD,
    route_after_reflection,
    route_after_verification,
)
from engines.research_agent.graph.state import make_initial_state


# ── make_initial_state ───────────────────────────────────────────────────────


class TestInitialState:
    def test_all_keys_present_with_defaults(self):
        state = make_initial_state(
            session_id="sid", query="What is GST?", user_id="uid"
        )
        assert state["session_id"] == "sid"
        assert state["query"] == "What is GST?"
        assert state["user_id"] == "uid"
        # Collections default to empty, scalars to safe zeros/False.
        assert state["sub_queries"] == []
        assert state["raw_search_results"] == []
        assert state["errors"] == []
        assert state["retry_count"] == 0
        assert state["verification_passed"] is False
        assert state["cancelled"] is False
        assert state["total_tokens_used"] == 0
        assert state["reflection_score"] == 0.0

    def test_anonymous_user_id_defaults_none(self):
        state = make_initial_state(session_id="sid", query="some query")
        assert state["user_id"] is None


# ── route_after_verification ─────────────────────────────────────────────────


class TestRouteAfterVerification:
    def _state(self, **over):
        state = make_initial_state(session_id="sid", query="q")
        state.update(over)
        return state

    def test_cancelled_ends(self):
        assert route_after_verification(self._state(cancelled=True)) == END

    def test_passed_goes_to_summary(self):
        state = self._state(verification_passed=True)
        assert route_after_verification(state) == "summary_generator"

    def test_failed_within_budget_retries_search(self):
        # retry_count == MAX (1) → router still allows one more search loop.
        state = self._state(
            verification_passed=False, retry_count=MAX_VERIFICATION_RETRIES
        )
        assert route_after_verification(state) == "search"

    def test_failed_budget_exhausted_proceeds(self):
        state = self._state(
            verification_passed=False, retry_count=MAX_VERIFICATION_RETRIES + 1
        )
        assert route_after_verification(state) == "summary_generator"


# ── route_after_reflection ───────────────────────────────────────────────────


class TestRouteAfterReflection:
    def _state(self, **over):
        state = make_initial_state(session_id="sid", query="q")
        state.update(over)
        return state

    def test_cancelled_ends(self):
        assert route_after_reflection(self._state(cancelled=True)) == END

    def test_high_score_ends(self):
        state = self._state(reflection_score=REFLECTION_THRESHOLD)
        assert route_after_reflection(state) == END

    def test_low_score_within_budget_replans(self):
        state = self._state(reflection_score=0.4, retry_count=MAX_REFLECTION_PASSES)
        assert route_after_reflection(state) == "planner"

    def test_low_score_budget_exhausted_ends(self):
        state = self._state(reflection_score=0.4, retry_count=MAX_REFLECTION_PASSES + 1)
        assert route_after_reflection(state) == END
