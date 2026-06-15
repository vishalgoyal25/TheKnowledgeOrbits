"""
engines/research_agent/tools/registry.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ToolRegistry — central catalog of all available tools.

Agents NEVER import tool classes directly. They call:
    registry.get("tavily")          → TavilyTool instance
    registry.get_search_chain()     → [TavilyTool, ExaTool, WikipediaTool]
    registry.get("calculator")      → CalculatorTool instance

This indirection means:
  - Swapping a provider = change registry, zero agent code changes
  - Circuit breaker state lives in one place (registry), not scattered across agents
  - All tools are instantiated ONCE at module level (singletons)

Module-level singleton `tool_registry` is what agents import.
"""

from __future__ import annotations

import structlog
import sentry_sdk

logger = structlog.get_logger(__name__)


class ToolRegistry:
    """
    Lazy-initializing registry. Tools are instantiated on first access,
    not at import time — prevents API key errors at startup if keys are missing.
    """

    def __init__(self) -> None:
        self._tools: dict = {}
        self._initialized = False

    def _initialize(self) -> None:
        """
        Instantiate all tools once. Called on first registry access.
        Import tool classes here (not at module top) to avoid circular imports
        during Django startup before settings are fully loaded.
        """
        if self._initialized:
            return

        try:
            from engines.research_agent.tools.tavily_tool import TavilyTool
            from engines.research_agent.tools.exa_tool import ExaTool
            from engines.research_agent.tools.wikipedia_tool import WikipediaTool
            from engines.research_agent.tools.calculator_tool import CalculatorTool
            from engines.research_agent.tools.domain_classifier import DomainClassifier
            from engines.research_agent.tools.credibility_scorer import (
                CredibilityScorer,
            )

            self._tools = {
                "tavily": TavilyTool(),
                "exa": ExaTool(),
                "wikipedia": WikipediaTool(),
                "calculator": CalculatorTool(),
                "domain": DomainClassifier(),
                "credibility": CredibilityScorer(),
            }

            self._initialized = True

            logger.info(
                "research_agent.tool_registry.initialized",
                tools=list(self._tools.keys()),
            )

        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error(
                "research_agent.tool_registry.init_failed",
                error=str(exc),
            )
            raise

    def get(self, name: str):
        """
        Returns a tool instance by name.
        Raises KeyError with a clear message if name is not registered.

        Usage:
            tool = registry.get("tavily")
            results = tool.search("What is Article 370?")
        """
        self._initialize()

        if name not in self._tools:
            raise KeyError(
                f"Tool '{name}' not found in registry. "
                f"Available tools: {list(self._tools.keys())}"
            )
        return self._tools[name]

    def get_search_chain(self) -> list:
        """
        Returns the ordered fallback chain for web search:
            [TavilyTool, ExaTool, WikipediaTool]

        The Search Agent iterates this list — tries each in order,
        moves to next only on failure (circuit breaker pattern).

        Order is intentional:
          1. Tavily   — best quality, freshest results, API quota applies
          2. Exa      — neural search, fallback when Tavily fails/quota hit
          3. Wikipedia — always available, no key, structured content
        """
        self._initialize()
        return [
            self._tools["tavily"],
            self._tools["exa"],
            self._tools["wikipedia"],
        ]

    def get_all(self) -> dict:
        """Returns all registered tools. Used by management command for health checks."""
        self._initialize()
        return dict(self._tools)


# Module-level singleton — agents import this directly:
#   from engines.research_agent.tools.registry import tool_registry
tool_registry = ToolRegistry()
