"""
engines/research_agent/llmops/langfuse_client.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LangfuseClient — LLMOps/AgentOps tracing (langfuse SDK 4.x, OTEL-based).

ONE trace per research session (trace_id derived deterministically from
session_id via `create_trace_id(seed=...)`), with ONE observation per agent and
per underlying LLM call — recording model, provider, tokens, duration, success,
prompt version. The dashboard a developer watches for cost/latency/quality.

API (langfuse 4.7.1): the SDK unifies spans/generations into ONE method,
`start_observation(name=, as_type="span"|"generation", trace_context={...}, ...)`,
returning an observation with `.update()` / `.end()`. (Older `start_span` /
`start_generation` do NOT exist in 4.x.)

NON-NEGOTIABLE: every method is wrapped in try/except + lazy SDK import. If keys
are missing or the API differs, everything is a silent no-op — the workflow runs
identically. flush() is called ONCE at session end (Risk #16). Metadata only, no
full prompts/reports (Risk #52).
"""

from __future__ import annotations

import contextvars

import structlog

logger = structlog.get_logger(__name__)

# Concurrency-safe call context: BaseAgent.run() sets (session_id, agent_name),
# groq_client reads it to attach per-call observations — no signature threading.
_call_ctx: contextvars.ContextVar = contextvars.ContextVar(
    "research_call_ctx", default=(None, None)
)


def set_call_context(session_id: str | None, agent_name: str | None = None) -> None:
    """Called by BaseAgent.run() at the start of each agent."""
    try:
        _call_ctx.set((session_id, agent_name))
    except Exception:
        pass


class LangfuseClient:
    """Module-level singleton. Builds the SDK client once, lazily."""

    def __init__(self) -> None:
        self._client = None
        self._initialized = False

    # ──────────────────────────────────────────────────────────────────────────
    # PUBLIC
    # ──────────────────────────────────────────────────────────────────────────
    def is_enabled(self) -> bool:
        return self._get_client() is not None

    def start_trace(
        self, session_id: str, query: str, user_id: str | None = None
    ) -> str | None:
        """
        Anchor the session's trace (root observation, input = the query). Returns
        the deterministic trace_id (stored on ResearchSession.langfuse_trace_id),
        or None if Langfuse is disabled. Called by the Supervisor.
        """
        client = self._get_client()
        if client is None:
            return None
        trace_id = self._trace_id(client, session_id)
        try:
            obs = client.start_observation(
                trace_context={"trace_id": trace_id},
                name="research_session",
                as_type="span",
                input={"query": (query or "")[:500]},
            )
            try:
                obs.update_trace(user_id=user_id, session_id=session_id)
            except Exception:
                pass
            obs.end()
        except Exception as exc:
            logger.debug("research_agent.langfuse.start_trace_failed", error=str(exc))
        return trace_id

    def log_agent_span(
        self,
        session_id: str,
        agent_name: str,
        provider: str | None,
        model: str | None,
        tokens: int,
        duration_ms: int,
        success: bool,
        prompt_version: str = "",
    ) -> None:
        """One observation per agent run (AgentOps trajectory + cost). Metadata only."""
        self._observe(
            session_id=session_id,
            name=agent_name,
            model=model,
            tokens=tokens,
            metadata={
                "provider": provider,
                "duration_ms": duration_ms,
                "success": success,
                "prompt_version": prompt_version,
            },
        )

    def log_llm_call(
        self,
        provider: str | None,
        model: str | None,
        tokens: int,
        duration_ms: int,
        failed_over: bool,
    ) -> None:
        """One observation per underlying LLM call (which provider, failover). Context-scoped."""
        session_id, agent_name = _call_ctx.get()
        if not session_id:
            return  # no session context → skip (don't create orphan traces)
        self._observe(
            session_id=session_id,
            name=f"{agent_name or 'agent'}:{provider}",
            model=model,
            tokens=tokens,
            metadata={
                "provider": provider,
                "duration_ms": duration_ms,
                "failed_over": failed_over,
            },
        )

    def flush(self) -> None:
        """Flush queued events. Called ONCE by the orchestrator at session end."""
        client = self._get_client()
        if client is None:
            return
        try:
            client.flush()
        except Exception as exc:
            logger.debug("research_agent.langfuse.flush_failed", error=str(exc))

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────────────────────────────────
    def _observe(
        self, session_id: str, name: str, model: str | None, tokens: int, metadata: dict
    ) -> None:
        """Create one 'generation' observation under the session's trace."""
        client = self._get_client()
        if client is None:
            return
        try:
            trace_id = self._trace_id(client, session_id)
            obs = client.start_observation(
                trace_context={"trace_id": trace_id},
                name=name,
                as_type="generation",
                model=model or "n/a",
                metadata=metadata,
                usage_details={"total": tokens or 0},
            )
            obs.end()
        except Exception as exc:
            logger.debug(
                "research_agent.langfuse.observe_failed", name=name, error=str(exc)
            )

    @staticmethod
    def _trace_id(client, session_id: str) -> str:
        """Deterministic trace_id from the session_id (same seed → same trace)."""
        try:
            return client.create_trace_id(seed=str(session_id))
        except Exception:
            return (str(session_id) or "").replace("-", "").lower()[:32]

    def _get_client(self):
        """Build the Langfuse client once. Returns None if disabled/unavailable."""
        if self._initialized:
            return self._client
        self._initialized = True
        try:
            from django.conf import settings

            public_key = getattr(settings, "LANGFUSE_PUBLIC_KEY", "") or ""
            secret_key = getattr(settings, "LANGFUSE_SECRET_KEY", "") or ""
            host = (
                getattr(settings, "LANGFUSE_HOST", "") or "https://cloud.langfuse.com"
            )

            if not public_key or not secret_key:
                logger.info(
                    "research_agent.langfuse.disabled", reason="keys_not_configured"
                )
                self._client = None
                return None

            from langfuse import Langfuse

            self._client = Langfuse(
                public_key=public_key, secret_key=secret_key, host=host
            )
            logger.info("research_agent.langfuse.enabled", host=host)
        except Exception as exc:
            logger.warning("research_agent.langfuse.init_failed", error=str(exc))
            self._client = None
        return self._client


# Module-level singleton.
langfuse_client = LangfuseClient()
