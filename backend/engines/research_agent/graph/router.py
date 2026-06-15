"""
engines/research_agent/graph/router.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Conditional edge routing functions for LangGraph.

These two functions are the ONLY decision points in the entire graph.
Everything else is a fixed linear flow.

Called by graph.py add_conditional_edges():
  - route_after_verification → decides: retry search OR proceed to summary
  - route_after_reflection   → decides: re-plan OR end workflow
"""

from __future__ import annotations

import structlog
from langgraph.graph import END

from engines.research_agent.graph.state import ResearchState
from engines.research_agent.constants import (
    MAX_VERIFICATION_RETRIES,
    MAX_REFLECTION_PASSES,
)

# Must match REFLECTION_PASS_THRESHOLD in reflection_agent.py.
REFLECTION_THRESHOLD = 0.7

logger = structlog.get_logger(__name__)


def route_after_verification(state: ResearchState) -> str:
    """
    Called after VerificationAgent completes.

    Decision logic:
      1. If cancelled → end immediately (user disconnected)
      2. If verification passed → proceed to summary_generator
      3. If failed AND retries remaining → go back to search (retry loop)
      4. If failed AND retries exhausted → proceed anyway (best-effort report)

    Returns: node name string matching the keys in add_conditional_edges map.
    """
    # Safety first — never do more work on a cancelled session
    if state.get("cancelled", False):
        logger.info(
            "research_agent.router.cancelled",
            session_id=state["session_id"],
            at="verification",
        )
        return END

    if state["verification_passed"]:
        logger.info(
            "research_agent.router.verification_passed",
            session_id=state["session_id"],
        )
        return "summary_generator"

    # Verification failed — check if we have retries left.
    # Verification increments retry_count on each fail, so `<=` yields exactly
    # MAX_VERIFICATION_RETRIES loops: fail#1→retry_count=1 (1<=1 retry),
    # fail#2→retry_count=2 (2<=1 give up). See VerificationAgent retry contract.
    if state["retry_count"] <= MAX_VERIFICATION_RETRIES:
        logger.warning(
            "research_agent.router.verification_retry",
            session_id=state["session_id"],
            retry_count=state["retry_count"],
            notes=state.get("verification_notes"),
        )
        return "search"

    # Retries exhausted — proceed with best-effort report
    logger.warning(
        "research_agent.router.verification_failed_proceeding",
        session_id=state["session_id"],
        retry_count=state["retry_count"],
    )
    return "summary_generator"


def route_after_reflection(state: ResearchState) -> str:
    """
    Called after ReflectionAgent completes.

    Decision logic:
      1. If cancelled → end immediately
      2. If reflection_score >= 0.7 → END (report is good enough)
      3. If reflection_score < 0.7 AND first time → re-plan (back to planner)
      4. If reflection_score < 0.7 AND already re-planned → END anyway
         (prevents infinite loop — max 1 re-plan pass)

    Returns: node name string or END sentinel.
    """
    if state.get("cancelled", False):
        logger.info(
            "research_agent.router.cancelled",
            session_id=state["session_id"],
            at="reflection",
        )
        return END

    score = state.get("reflection_score", 0.0)

    if score >= REFLECTION_THRESHOLD:
        logger.info(
            "research_agent.router.reflection_passed",
            session_id=state["session_id"],
            score=score,
        )
        return END

    # Score too low — re-plan only while the shared corrective-loop budget lasts.
    # Reflection increments retry_count on each low score, so `<=` yields a
    # bounded number of re-plans and can never loop forever. retry_count is
    # SHARED with verification retries, so a run that already retried search
    # won't also re-plan — total corrective loops stay bounded.
    if state["retry_count"] <= MAX_REFLECTION_PASSES:
        logger.warning(
            "research_agent.router.reflection_replan",
            session_id=state["session_id"],
            score=score,
            retry_count=state["retry_count"],
            notes=state.get("reflection_notes"),
        )
        return "planner"

    # Budget spent — end regardless of score (best-effort).
    logger.warning(
        "research_agent.router.reflection_low_score_ending",
        session_id=state["session_id"],
        score=score,
    )
    return END
