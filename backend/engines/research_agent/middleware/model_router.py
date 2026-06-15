"""
engines/research_agent/middleware/model_router.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ModelRouter — the single source of truth for WHICH model each agent uses, plus a
Redis-backed provider health flag (a lightweight circuit breaker).

Routing philosophy (already reflected in the agents' class attributes; this is
the documented, queryable central map):
  - Heavy reasoning / synthesis / report  → Groq  llama-3.3-70b-versatile (quality)
  - Fast judgement / summary / reflection  → Cerebras gpt-oss-120b (speed)
  - Tool-only nodes (search)               → no LLM

The actual cross-provider FAILOVER lives in llmops/groq_client.py (the pool).
This router supplements it with a health flag: when a provider fails repeatedly,
mark it unhealthy for a short cooldown so callers can prefer the other one.
"""

from __future__ import annotations

import structlog

from engines.research_agent.constants import (
    AgentName,
    MAX_TOKENS_SUPERVISOR,
    MAX_TOKENS_PLANNER,
    MAX_TOKENS_RESEARCH,
    MAX_TOKENS_VERIFICATION,
    MAX_TOKENS_REPORT_GENERATOR,
    MAX_TOKENS_REFLECTION,
    MAX_TOKENS_SUMMARY,
)

logger = structlog.get_logger(__name__)

_GROQ = "groq"
_CEREBRAS = "cerebras"
_GROQ_MODEL = "llama-3.3-70b-versatile"
_CEREBRAS_MODEL = "gpt-oss-120b"

# Per-agent model assignment (mirrors each agent's class attributes).
_AGENT_MODEL_MAP: dict[str, dict] = {
    AgentName.SUPERVISOR: {
        "provider": _GROQ,
        "model": _GROQ_MODEL,
        "max_tokens": MAX_TOKENS_SUPERVISOR,
    },
    AgentName.PLANNER: {
        "provider": _GROQ,
        "model": _GROQ_MODEL,
        "max_tokens": MAX_TOKENS_PLANNER,
    },
    AgentName.SEARCH: {
        "provider": None,
        "model": None,
        "max_tokens": 0,
    },  # tool-only, no LLM
    AgentName.RESEARCH: {
        "provider": _GROQ,
        "model": _GROQ_MODEL,
        "max_tokens": MAX_TOKENS_RESEARCH,
    },
    AgentName.VERIFICATION: {
        "provider": _CEREBRAS,
        "model": _CEREBRAS_MODEL,
        "max_tokens": MAX_TOKENS_VERIFICATION,
    },
    AgentName.SUMMARY_GENERATOR: {
        "provider": _CEREBRAS,
        "model": _CEREBRAS_MODEL,
        "max_tokens": MAX_TOKENS_SUMMARY,
    },
    AgentName.REPORT_GENERATOR: {
        "provider": _GROQ,
        "model": _GROQ_MODEL,
        "max_tokens": MAX_TOKENS_REPORT_GENERATOR,
    },
    AgentName.REFLECTION: {
        "provider": _CEREBRAS,
        "model": _CEREBRAS_MODEL,
        "max_tokens": MAX_TOKENS_REFLECTION,
    },
}

_DEFAULT_CONFIG = {"provider": _GROQ, "model": _GROQ_MODEL, "max_tokens": 1024}

_HEALTH_KEY = "research:provider:unhealthy:{provider}"
_HEALTH_COOLDOWN = 60  # seconds a provider stays flagged unhealthy


class ModelRouter:
    """Module-level singleton. Config is static; health is Redis-backed."""

    def get_model_config(self, agent_name: str) -> dict:
        """Return {provider, model, max_tokens} for an agent (default if unknown)."""
        return dict(_AGENT_MODEL_MAP.get(agent_name, _DEFAULT_CONFIG))

    # ── Provider health (lightweight circuit breaker) ──────────────────────────
    def mark_unhealthy(self, provider: str) -> None:
        """Flag a provider as unhealthy for a short cooldown after repeated failures."""
        conn = self._redis()
        if conn is None:
            return
        try:
            conn.set(_HEALTH_KEY.format(provider=provider), "1", ex=_HEALTH_COOLDOWN)
            logger.warning(
                "research_agent.model_router.provider_unhealthy", provider=provider
            )
        except Exception:
            pass

    def is_provider_healthy(self, provider: str) -> bool:
        """True unless the provider is currently flagged unhealthy. Fails healthy."""
        conn = self._redis()
        if conn is None:
            return True
        try:
            return conn.exists(_HEALTH_KEY.format(provider=provider)) == 0
        except Exception:
            return True

    def _redis(self):
        try:
            from django_redis import get_redis_connection

            return get_redis_connection("default")
        except Exception:
            return None


# Module-level singleton.
model_router = ModelRouter()
