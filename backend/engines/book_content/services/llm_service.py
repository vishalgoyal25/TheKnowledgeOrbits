"""
engines/book_content/services/llm_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Unified multi-provider LLM client — shared by all engines.

Active provider pool (round-robin rotation):
  • GROQ      — api.groq.com        — llama-3.3-70b-versatile  (primary, free)
  • Cerebras  — api.cerebras.ai/v1  — llama3.1-8b              (additive, free)

Excluded providers:
  • Gemini  — 15 RPM free-tier cap makes it unsuitable for round-robin pool
  • Together AI — paid credits only

SDK choice per provider (all expose identical .chat.completions.create() API):
  • GROQ      → groq.Groq            (native SDK)
  • Cerebras  → cerebras.cloud.sdk.Cerebras (native SDK — NOT groq.Groq; groq SDK
                hardcodes /openai/v1/ path prefix which 404s against Cerebras)
  • Gemini    → openai.OpenAI(base_url=...) (Google exposes OpenAI-compat endpoint)
  • Others    → openai.OpenAI(base_url=...) (Together AI, Mistral, etc. same pattern)

Adding a new provider:
  1. Add KEY to .env  +  settings/base.py
  2. Uncomment / append a block in _build_pool() — zero changes elsewhere.

Ported from: upsc-agent-lab/src/llm_client.py
Changes: multi-provider support, native SDKs per provider
Preserved exactly: rate limits, retry logic, key-rotation algorithm.
"""

import time
from dataclasses import dataclass
from typing import Any

from django.conf import settings

import sentry_sdk
import structlog
from cerebras.cloud.sdk import Cerebras  # cerebras-cloud-sdk>=1.67.0
from groq import Groq

logger = structlog.get_logger(__name__)

# ── Rate Limit Config ─────────────────────────────────────────────────────────
# 12 s soft throttle keeps us under GROQ free tier's 6 000 tokens/min.
# Cerebras is more generous but sharing one sleep keeps logic simple.
INTER_CALL_SLEEP = 12.0
RETRY_WAIT_TIMES = [15, 30, 60, 120]  # Cooldown ladder when all keys are 429

# Temperature / token settings per call mode
_MODE_CONFIG: dict[str, dict] = {
    "writer": {"temperature": 0.25, "max_tokens": 2048},
    "critique": {"temperature": 0.10, "max_tokens": 2048},
    "standard": {"temperature": 0.10, "max_tokens": 2048},
    "quiz": {"temperature": 0.70, "max_tokens": 4000},  # quiz / assessment generation
    "article": {"temperature": 0.70, "max_tokens": 2000},  # article_generation engine
}


# ── Provider Entry ────────────────────────────────────────────────────────────


@dataclass
class _LLMEntry:
    """One API key + its provider metadata."""

    client: Any  # Groq | Cerebras | OpenAI — all share .chat.completions.create()
    model: str
    provider: str


# ── Pool Builder ──────────────────────────────────────────────────────────────


def _build_pool() -> list[_LLMEntry]:
    """
    Reads all configured LLM keys from Django settings and returns a flat
    ordered list.  GROQ keys come first (primary quota), then Cerebras, then
    any future providers.

    To add a new provider: append a block following the same pattern.
    """
    pool: list[_LLMEntry] = []

    # ── GROQ (primary) ────────────────────────────────────────────────────────
    groq_model = getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")
    raw_groq = getattr(settings, "GROQ_API_KEY", "")
    for key in [k.strip() for k in raw_groq.split(",") if k.strip()]:
        pool.append(
            _LLMEntry(
                client=Groq(api_key=key),
                model=groq_model,
                provider="groq",
            )
        )

    # ── Cerebras (additive) ───────────────────────────────────────────────────
    # Uses cerebras.cloud.sdk.Cerebras — the official first-party SDK.
    # Do NOT use groq.Groq here: groq SDK hardcodes "/openai/v1/" path prefix,
    # which produces https://api.cerebras.ai/v1/openai/v1/... → 404.
    # The Cerebras SDK knows its own endpoint; no base_url override needed.
    raw_cerebras = getattr(settings, "CEREBRAS_API_KEY", "")
    for key in [k.strip() for k in raw_cerebras.split(",") if k.strip()]:
        pool.append(
            _LLMEntry(
                client=Cerebras(api_key=key),
                model="llama3.1-8b",  # Cerebras available model (llama3.3-70b not on this account)
                provider="cerebras",
            )
        )

    # ── Google Gemini (excluded — 15 RPM free-tier cap too tight for pool) ──────
    # Keep key in settings for future use if Google raises free limits.
    # raw_gemini = getattr(settings, "GEMINI_API_KEY", "")
    # for key in [k.strip() for k in raw_gemini.split(",") if k.strip()]:
    #     pool.append(_LLMEntry(
    #         client=OpenAI(api_key=key,
    #                       base_url="https://generativelanguage.googleapis.com/v1beta/openai/"),
    #         model="gemini-2.0-flash", provider="gemini",
    #     ))

    # ── Fallback (prevents startup crash when no keys configured) ─────────────
    if not pool:
        logger.error("llm_pool_empty", message="No LLM API keys found in settings!")
        pool.append(
            _LLMEntry(
                client=Groq(api_key="DUMMY_KEY"),
                model=groq_model,
                provider="groq",
            )
        )
        return pool

    providers_summary: dict[str, int] = {}
    for entry in pool:
        providers_summary[entry.provider] = providers_summary.get(entry.provider, 0) + 1
    logger.info("llm_pool_initialized", total=len(pool), providers=providers_summary)

    return pool


# ── Module-level pool (built once at first import) ────────────────────────────
_pool: list[_LLMEntry] = _build_pool()
_pool_size: int = len(_pool)
_current_key_idx: int = 0


# ── Core Call Wrapper ─────────────────────────────────────────────────────────


def llm_call(prompt: str, mode: str = "standard") -> str:
    """
    Makes one LLM call using the unified round-robin multi-provider pool.

    Args:
        prompt: Full prompt string.
        mode:   'standard' | 'writer' | 'critique'
                  writer   — temperature 0.25 (article generation)
                  critique — temperature 0.10 (self-critique pass)
                  standard — temperature 0.10 (classification, planning)

    Returns:
        Response string.  Empty string on permanent failure (all keys/providers
        exhausted after all retry attempts).

    Retry behaviour:
        - On 429 / any exception: rotate to next key immediately.
        - When all keys have been tried once (full loop): sleep (exponential ladder).
        - After max_retries attempts: log, Sentry alert, return "".
    """
    global _current_key_idx

    # Soft throttle — keeps GROQ free tier under 6 000 tokens/min.
    time.sleep(INTER_CALL_SLEEP)

    cfg = _MODE_CONFIG.get(mode, _MODE_CONFIG["standard"])
    max_retries = len(RETRY_WAIT_TIMES) * _pool_size

    for attempt in range(max_retries):
        key_idx = _current_key_idx % _pool_size
        entry = _pool[key_idx]

        try:
            response = entry.client.chat.completions.create(
                model=entry.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=cfg["temperature"],
                max_tokens=cfg["max_tokens"],
            )
            content = (response.choices[0].message.content or "").strip()

            logger.info(
                "llm_call_success",
                chars=len(content),
                mode=mode,
                key_idx=key_idx,
                provider=entry.provider,
            )

            # Rotate on success — spread load across all keys
            _current_key_idx = (key_idx + 1) % _pool_size
            return content

        except Exception as e:
            err = str(e).replace("\n", " ")
            logger.warning(
                "llm_call_failed",
                key_idx=key_idx,
                provider=entry.provider,
                attempt=attempt + 1,
                error=err[:80],
            )

            last_idx = key_idx
            _current_key_idx = (key_idx + 1) % _pool_size

            # Detect full loop (every key tried once) → enter cooldown
            if _current_key_idx <= last_idx:
                wait_idx = attempt // _pool_size
                if wait_idx < len(RETRY_WAIT_TIMES):
                    wait = RETRY_WAIT_TIMES[wait_idx]
                    logger.warning(
                        "llm_all_keys_exhausted",
                        num_keys=_pool_size,
                        cooldown_seconds=wait,
                    )
                    time.sleep(wait)

    logger.error("llm_permanently_failed", max_retries=max_retries, num_keys=_pool_size)
    sentry_sdk.capture_message(
        f"LLM permanently failed after {max_retries} attempts across {_pool_size} keys.",
        level="error",
    )
    return ""


def llm_call_json(
    prompt: str,
    system_prompt: str = "",
    mode: str = "standard",
) -> str:
    """
    Like llm_call() but passes a system message and requests JSON output.
    Used by: assessment/quiz_generator.py

    Passes response_format={"type": "json_object"} to providers that support it
    (GROQ).  If a provider rejects it, the exception is caught and the next key
    is tried — same retry/rotation logic as llm_call().

    Returns:
        Raw JSON string (caller is responsible for json.loads).
        Empty string on permanent failure.
    """
    global _current_key_idx

    time.sleep(INTER_CALL_SLEEP)

    cfg = _MODE_CONFIG.get(mode, _MODE_CONFIG["standard"])
    max_retries = len(RETRY_WAIT_TIMES) * _pool_size

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    for attempt in range(max_retries):
        key_idx = _current_key_idx % _pool_size
        entry = _pool[key_idx]

        try:
            response = entry.client.chat.completions.create(
                model=entry.model,
                messages=messages,
                temperature=cfg["temperature"],
                max_tokens=cfg["max_tokens"],
                response_format={"type": "json_object"},
            )
            content = (response.choices[0].message.content or "").strip()

            logger.info(
                "llm_call_json_success",
                chars=len(content),
                mode=mode,
                key_idx=key_idx,
                provider=entry.provider,
            )

            _current_key_idx = (key_idx + 1) % _pool_size
            return content

        except Exception as e:
            err = str(e).replace("\n", " ")
            logger.warning(
                "llm_call_json_failed",
                key_idx=key_idx,
                provider=entry.provider,
                attempt=attempt + 1,
                error=err[:80],
            )

            last_idx = key_idx
            _current_key_idx = (key_idx + 1) % _pool_size

            if _current_key_idx <= last_idx:
                wait_idx = attempt // _pool_size
                if wait_idx < len(RETRY_WAIT_TIMES):
                    wait = RETRY_WAIT_TIMES[wait_idx]
                    logger.warning(
                        "llm_all_keys_exhausted",
                        num_keys=_pool_size,
                        cooldown_seconds=wait,
                    )
                    time.sleep(wait)

    logger.error(
        "llm_json_permanently_failed", max_retries=max_retries, num_keys=_pool_size
    )
    sentry_sdk.capture_message(
        f"LLM JSON call permanently failed after {max_retries} attempts across {_pool_size} keys.",
        level="error",
    )
    return ""
