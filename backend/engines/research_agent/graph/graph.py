"""
engines/research_agent/graph/graph.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LangGraph StateGraph — wires all 7 agent nodes into one compiled workflow.

Topology:
  START
    └─► supervisor
          └─► planner
                └─► search
                      └─► research
                            └─► verification
                                  ├─► [retry: back to search]   if failed & retry_count < 1
                                  └─► summary_generator          if passed (or retry exhausted)
                                        └─► report_generator
                                              └─► reflection
                                                    ├─► [re-plan: back to planner]  if score < 0.7
                                                    └─► END                          if score >= 0.7

Key rules:
  - compiled_graph is a MODULE-LEVEL singleton — built once, reused across all requests.
  - Checkpointing via PostgresSaver (existing DB) — enables workflow resume on crash.
  - LANGCHAIN_TRACING_V2=false — LangSmith explicitly disabled (Risk #22).
"""

from __future__ import annotations

import os
import structlog
from langgraph.graph import StateGraph, START, END

from engines.research_agent.graph.state import ResearchState
from engines.research_agent.graph.router import (
    route_after_verification,
    route_after_reflection,
)
from engines.research_agent.graph.checkpointer import get_checkpointer

from engines.research_agent.agents.supervisor_agent import SupervisorAgent
from engines.research_agent.agents.planner_agent import PlannerAgent
from engines.research_agent.agents.search_agent import SearchAgent
from engines.research_agent.agents.research_agent_node import ResearchAgentNode
from engines.research_agent.agents.verification_agent import VerificationAgent
from engines.research_agent.agents.summary_generator import SummaryGeneratorAgent
from engines.research_agent.agents.report_generator import ReportGeneratorAgent
from engines.research_agent.agents.reflection_agent import ReflectionAgent

logger = structlog.get_logger(__name__)

# ── Disable LangSmith tracing (Risk #22 — must never be enabled in production) ──
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")

# ── Agent singletons (instantiated once at module load) ───────────────────────
_supervisor = SupervisorAgent()
_planner = PlannerAgent()
_search = SearchAgent()
_research = ResearchAgentNode()
_verification = VerificationAgent()
_summary_generator = SummaryGeneratorAgent()
_report_generator = ReportGeneratorAgent()
_reflection = ReflectionAgent()

# ── Module-level compiled graph singleton ────────────────────────────────────
_compiled_graph = None


def _build_graph():
    """
    Builds and compiles the LangGraph StateGraph.
    Called once at startup. Result cached in _compiled_graph.

    Each .add_node(name, fn) registers an agent's .run() method as a node.
    Each .add_edge(a, b) means: after node a completes, always go to node b.
    .add_conditional_edges: router function decides which node to go to next.
    """
    logger.info("research_agent.graph.building")

    graph = StateGraph(ResearchState)

    # ── Register all 7 agent nodes ────────────────────────────────────────────
    graph.add_node("supervisor", _supervisor.run)
    graph.add_node("planner", _planner.run)
    graph.add_node("search", _search.run)
    graph.add_node("research", _research.run)
    graph.add_node("verification", _verification.run)
    graph.add_node("summary_generator", _summary_generator.run)
    graph.add_node("report_generator", _report_generator.run)
    graph.add_node("reflection", _reflection.run)

    # ── Fixed edges (always go to the next node) ──────────────────────────────
    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", "planner")
    graph.add_edge("planner", "search")
    graph.add_edge("search", "research")
    graph.add_edge("research", "verification")
    # verification → conditional (see router.py)
    graph.add_edge("summary_generator", "report_generator")
    graph.add_edge("report_generator", "reflection")
    # reflection → conditional (see router.py)

    # ── Conditional edges (router decides the branch) ─────────────────────────
    graph.add_conditional_edges(
        "verification",
        route_after_verification,
        {
            "summary_generator": "summary_generator",  # passed (or retry exhausted) → proceed
            "search": "search",  # failed + budget left → go back
            END: END,  # cancelled → stop immediately
        },
    )

    graph.add_conditional_edges(
        "reflection",
        route_after_reflection,
        {
            "planner": "planner",  # score < 0.7 → re-plan once
            END: END,  # score >= 0.7 → done
        },
    )

    # ── Compile with PostgreSQL checkpointer ──────────────────────────────────
    checkpointer = get_checkpointer()

    compiled = graph.compile(checkpointer=checkpointer)

    logger.info("research_agent.graph.compiled")
    return compiled


def get_compiled_graph():
    """
    Returns the module-level compiled graph singleton.
    Builds it on first call, reuses on all subsequent calls.

    Called by: ResearchOrchestrator.run()
    Thread-safe: LangGraph compiled graphs are immutable after compile().
    """
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_graph()
    return _compiled_graph
