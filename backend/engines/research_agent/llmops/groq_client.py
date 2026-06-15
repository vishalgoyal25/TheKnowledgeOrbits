"""
engines/research_agent/llmops/groq_client.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The single LLM phone line for the whole research_agent engine.

Despite the file name, this is a MULTI-PROVIDER POOL with automatic failover.
ALL LLM calls MUST route through here (Hard Rule, Risk #3).

THE POOL (free-tier providers, in failover priority order):
    1. groq      → llama-3.3-70b-versatile   (primary: fast + high quality)
    2. cerebras  → gpt-oss-120b              (free public model: Verification/Reflection/Summary)
    3. gemini    → gemini-2.0-flash          (last-resort fallback)

TWO LAYERS OF RESILIENCE (same idea as the Tavily→Exa→Wikipedia search chain):

  Layer 1 — RETRY (transient hiccup):
      A provider call that fails (rate limit, timeout, 5xx) is retried a few
      times with exponential backoff against the SAME provider.

  Layer 2 — FAILOVER (provider down):
      If a provider still fails after all retries (or its key is missing),
      we move to the NEXT provider in the pool. The agent that asked for
      "cerebras" silently gets "groq" instead — it never sees the failure.

An agent states a PREFERENCE (provider=...); the pool guarantees an ANSWER
as long as at least one provider in the pool is alive.

HOOKS for later phases (intentionally left as clearly-marked no-ops):
  - _check_rate_limit()  → Redis token bucket            (Phase 6)
  - Langfuse span wrap   → trace every call              (Phase 7)
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from django.conf import settings
from tenacity import (
    Retrying,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = structlog.get_logger(__name__)

# ── Pool configuration ────────────────────────────────────────────────────────
# Global failover priority. The agent's preferred provider is tried FIRST,
# then the remaining enabled providers in this order.
# Gemini is intentionally OUT of the pool (its free tier is unusable: quota 0).
# Focus: Groq + Cerebras. So every agent ultimately falls back between these two.
POOL_PRIORITY = ["groq", "cerebras"]

# Each provider's default model — used when failing over to a provider the
# agent didn't originally request (the requested model name is provider-specific
# and won't exist on a different provider).
PROVIDER_DEFAULT_MODEL = {
    "groq": "llama-3.3-70b-versatile",
    "cerebras": "gpt-oss-120b",  # Cerebras retired Llama on public endpoints; this is the free production model
    "gemini": "gemini-2.0-flash",  # kept for easy re-enable, but not in POOL_PRIORITY
}

# Retry policy PER PROVIDER (Layer 1). Kept small so a fully-dead provider
# fails fast and we move on — worst case across 3 providers stays well under
# the Celery soft time limit.
MAX_RETRIES_PER_PROVIDER = 2
RETRY_WAIT_MIN = 1  # seconds
RETRY_WAIT_MAX = 4  # seconds

# Sentinel values that mean "this key is not really configured".
_DISABLED_KEY_VALUES = {"", "dummy-key-for-build", None}


class LLMError(Exception):
    """Raised only when EVERY provider in the pool has failed."""

    pass


class LLMClient:
    """
    Module-level singleton. Stateless per call — safe to share across agents.
    Provider SDK clients are lazily built once and cached.
    """

    def __init__(self) -> None:
        # Cache SDK clients keyed by the ACTUAL api key string (not by provider),
        # because a provider can have a POOL of comma-separated keys we rotate.
        self._clients: dict = {}  # api_key_string → SDK client instance
        self._rr_index: dict = {}  # provider → next round-robin index

    # ──────────────────────────────────────────────────────────────────────────
    # PUBLIC — what BaseAgent._call_llm() calls.
    # ──────────────────────────────────────────────────────────────────────────
    def call(
        self,
        prompt: str,
        system: str | None = None,
        provider: str = "groq",
        model: str | None = None,
        max_tokens: int = 1024,
        response_format: dict | None = None,
    ) -> tuple[str, int]:
        """
        Get a completion, with retry + failover across the whole pool.

        Args:
            prompt:     user message.
            system:     optional system prompt.
            provider:   PREFERRED provider (tried first).
            model:      model for the preferred provider (provider default if None).
            max_tokens: hard cap on output tokens.
            response_format: optional, e.g. {"type": "json_object"} to force valid
                             JSON output (used by structured-output agents — both
                             Groq and Cerebras support it; eliminates the bad-JSON
                             parse failures on gpt-oss).

        Returns:
            (response_text, tokens_used)

        Raises:
            LLMError: only if every provider in the pool failed.
        """
        messages = self._build_messages(prompt, system)
        last_error: Exception | None = None

        for prov in self._failover_order(provider):
            # On the preferred provider, honor the requested model; on a
            # fallback provider, use that provider's own default model.
            prov_model = model if prov == provider else None
            prov_model = prov_model or PROVIDER_DEFAULT_MODEL[prov]

            try:
                self._check_rate_limit(prov)  # Redis RPM limiter (Phase 6)
                t0 = time.perf_counter()
                text, tokens = self._invoke_with_retry(
                    prov, messages, prov_model, max_tokens, response_format
                )
                duration_ms = int((time.perf_counter() - t0) * 1000)
                failed_over = prov != provider
                logger.info(
                    "research_agent.llm.call_ok",
                    provider=prov,
                    model=prov_model,
                    tokens=tokens,
                    failed_over=failed_over,
                )
                self._trace_call(prov, prov_model, tokens, duration_ms, failed_over)
                return text, tokens

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "research_agent.llm.provider_failed",
                    provider=prov,
                    error=str(exc),
                )
                continue  # → try next provider in the pool

        # Every provider failed.
        raise LLMError(
            f"All LLM providers failed. Last error: {last_error}"
        ) from last_error

    def call_stream(
        self,
        prompt: str,
        system: str | None = None,
        provider: str = "groq",
        model: str | None = None,
        max_tokens: int = 1500,
    ):
        """
        Streaming generator — yields text chunks as they arrive.
        Used by the Report Generator to stream tokens to the user via SSE.

        Failover happens only BEFORE the first chunk is yielded. Once a stream
        has started emitting, we cannot transparently switch providers, so a
        mid-stream failure raises LLMError.

        Yields:
            str chunks of the response.
        """
        messages = self._build_messages(prompt, system)
        last_error: Exception | None = None

        for prov in self._failover_order(provider):
            prov_model = model if prov == provider else None
            prov_model = prov_model or PROVIDER_DEFAULT_MODEL[prov]

            try:
                self._check_rate_limit(prov)
                client = self._get_client(prov)
                t0 = time.perf_counter()
                stream = client.chat.completions.create(
                    model=prov_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    stream=True,
                )
                logger.info(
                    "research_agent.llm.stream_start",
                    provider=prov,
                    model=prov_model,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
                # Stream finished cleanly — record the call (tokens not exposed
                # by streaming responses, so 0 here; the agent logs an estimate).
                duration_ms = int((time.perf_counter() - t0) * 1000)
                self._trace_call(prov, prov_model, 0, duration_ms, prov != provider)
                return

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "research_agent.llm.stream_provider_failed",
                    provider=prov,
                    error=str(exc),
                )
                continue

        raise LLMError(
            f"All LLM providers failed during streaming. Last error: {last_error}"
        ) from last_error

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE — pool mechanics.
    # ──────────────────────────────────────────────────────────────────────────
    def _failover_order(self, preferred: str) -> list[str]:
        """
        Build the ordered list of providers to try: preferred first, then the
        rest of the pool, skipping any provider whose API key isn't configured.
        """
        if preferred not in POOL_PRIORITY:
            preferred = "groq"

        ordered = [preferred] + [p for p in POOL_PRIORITY if p != preferred]
        enabled = [p for p in ordered if self._is_enabled(p)]

        if not enabled:
            raise LLMError(
                "No LLM providers are configured. Set at least one of "
                "GROQ_API_KEY / CEREBRAS_API_KEY / GEMINI_API_KEY."
            )
        return enabled

    def _is_enabled(self, provider: str) -> bool:
        """A provider is usable only if it has at least one real key configured."""
        return len(self._get_keys(provider)) > 0

    def _get_keys(self, provider: str) -> list[str]:
        """
        Return this provider's pool of API keys.

        Keys are stored COMMA-SEPARATED in settings (the project convention for
        multi-key pools, e.g. "gsk_aaa,gsk_bbb,gsk_ccc"). We split, strip, and
        drop blanks/placeholders. A single key just yields a 1-element list.
        """
        raw = {
            "groq": getattr(settings, "GROQ_API_KEY", ""),
            "cerebras": getattr(settings, "CEREBRAS_API_KEY", ""),
            "gemini": getattr(settings, "GEMINI_API_KEY", ""),
        }.get(provider, "") or ""

        return [
            k.strip()
            for k in raw.split(",")
            if k.strip() and k.strip() not in _DISABLED_KEY_VALUES
        ]

    def _next_key(self, provider: str) -> str:
        """
        Round-robin pick the next key from the provider's pool. Rotating spreads
        load across keys → effectively multiplies the free-tier rate limit, and
        means a retry naturally lands on a DIFFERENT key (helps when one key is
        momentarily rate-limited).
        """
        keys = self._get_keys(provider)
        if not keys:
            raise LLMError(f"No API keys configured for provider '{provider}'.")
        i = self._rr_index.get(provider, 0)
        self._rr_index[provider] = i + 1
        return keys[i % len(keys)]

    def _invoke_with_retry(
        self,
        provider: str,
        messages: list[dict],
        model: str,
        max_tokens: int,
        response_format: dict | None = None,
    ) -> tuple[str, int]:
        """
        Layer 1 — retry the SAME provider a few times with exponential backoff
        before giving up and letting the caller fail over.
        """
        retryer = Retrying(
            stop=stop_after_attempt(MAX_RETRIES_PER_PROVIDER),
            wait=wait_exponential(multiplier=1, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )
        return retryer(
            self._invoke, provider, messages, model, max_tokens, response_format
        )

    def _invoke(
        self,
        provider: str,
        messages: list[dict],
        model: str,
        max_tokens: int,
        response_format: dict | None = None,
    ) -> tuple[str, int]:
        """
        One actual completion call. All three providers expose the same
        OpenAI-compatible `chat.completions.create` interface, so a single
        code path handles them all.
        """
        client = self._get_client(provider)
        kwargs: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format
        resp = client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or ""
        tokens = self._extract_tokens(resp)
        return text, tokens

    def _get_client(self, provider: str):
        """
        Round-robin pick a key from the provider's pool, then build (and cache by
        key) that key's SDK client. SDKs are imported inside the branch so a
        missing optional SDK for one provider never breaks the others.
        """
        key = self._next_key(provider)

        if key in self._clients:
            return self._clients[key]

        # One of three different SDK client types depending on provider.
        client: Any
        if provider == "groq":
            from groq import Groq

            client = Groq(api_key=key)
        elif provider == "cerebras":
            from cerebras.cloud.sdk import Cerebras

            client = Cerebras(api_key=key)
        elif provider == "gemini":
            # Gemini exposes an OpenAI-compatible endpoint.
            from openai import OpenAI

            client = OpenAI(
                api_key=key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            )
        else:
            raise LLMError(f"Unknown provider: {provider}")

        self._clients[key] = client
        return client

    @staticmethod
    def _build_messages(prompt: str, system: str | None) -> list[dict]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    @staticmethod
    def _extract_tokens(resp) -> int:
        """Pull total token count from the response usage block (0 if absent)."""
        usage = getattr(resp, "usage", None)
        if usage is None:
            return 0
        return getattr(usage, "total_tokens", 0) or 0

    def _trace_call(
        self,
        provider: str,
        model: str,
        tokens: int,
        duration_ms: int,
        failed_over: bool,
    ) -> None:
        """
        Log this underlying LLM call as a Langfuse span (Phase 7). Reads the
        session/agent from the call context. Lazily imported + fully defensive —
        tracing must NEVER break or slow the LLM path.
        """
        try:
            from engines.research_agent.llmops.langfuse_client import langfuse_client

            langfuse_client.log_llm_call(
                provider=provider,
                model=model,
                tokens=tokens,
                duration_ms=duration_ms,
                failed_over=failed_over,
            )
        except Exception:
            pass

    def _check_rate_limit(self, provider: str) -> None:
        """
        Redis-backed per-provider RPM limiter (Phase 6). Raises RateLimitExceeded
        when this provider is at its per-minute cap → the failover loop in call()
        catches it and SKIPS to the next provider (pre-emptive load spreading,
        avoids upstream 429s). Lazily imported to avoid an import cycle.
        """
        from engines.research_agent.middleware.rate_limiter import rate_limiter

        rate_limiter.check_provider_rpm(provider)


# Module-level singleton — imported by BaseAgent._call_llm():
#   from engines.research_agent.llmops.groq_client import llm_client
llm_client = LLMClient()
