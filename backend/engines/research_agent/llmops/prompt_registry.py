"""
engines/research_agent/llmops/prompt_registry.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PromptRegistry — versioned prompt tracking for every agent.

Each agent's system prompt has a VERSION string. The version is attached to that
agent's Langfuse span, so when you change a prompt and quality shifts, you can
see in the dashboard exactly which prompt version produced which results
(the foundation for A/B testing and prompt CI later).

Why a registry (not just inline prompts)?
  - Single source of truth for "which prompt version is live."
  - Reproducibility — every trace records the version it ran.
  - Future: load templates from Langfuse-managed prompts / hot-swap without deploy.

For now prompts still live next to each agent (battle-tested); this registry
tracks their VERSIONS and exposes a place to centralize templates later.
"""

from __future__ import annotations

import structlog

from engines.research_agent.constants import AgentName

logger = structlog.get_logger(__name__)

# Current live prompt version per agent. Bump the string whenever you change an
# agent's prompt — the new version then appears on its Langfuse spans.
_PROMPT_VERSIONS: dict[str, str] = {
    AgentName.SUPERVISOR: "v1-validation",
    AgentName.PLANNER: "v2-json-subqueries",
    AgentName.SEARCH: "n/a-tool-only",
    AgentName.RESEARCH: "v2-json-citation-rules",
    AgentName.VERIFICATION: "v2-json-grounding-judge",
    AgentName.SUMMARY_GENERATOR: "v1-prose-300w",
    AgentName.REPORT_GENERATOR: "v2-grounded-800w",
    AgentName.REFLECTION: "v2-json-score",
}

_DEFAULT_VERSION = "v1"


class PromptRegistry:
    """Module-level singleton. Lightweight version tracker."""

    def get_version(self, agent_name: str) -> str:
        """Return the live prompt version string for an agent."""
        return _PROMPT_VERSIONS.get(agent_name, _DEFAULT_VERSION)

    def list_versions(self) -> dict[str, str]:
        """All agent → version mappings (admin / debugging)."""
        return dict(_PROMPT_VERSIONS)


# Module-level singleton.
prompt_registry = PromptRegistry()
