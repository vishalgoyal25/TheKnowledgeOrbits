"""
engines/book_content/services/llm_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Unified multi-provider LLM client — shared by every engine except research_agent
(which has its own isolated pool at research_agent/llmops/groq_client.py).

PROVIDER REGISTRY (see PROVIDERS below — the single source of truth):
  • groq        openai/gpt-oss-120b     ~5.5k token cap   small calls (primary)
  • mistral     mistral-medium-2508      ~120k cap        large calls (primary)
  • openrouter  minimax/minimax-m3:free  ~900k cap        emergency fallback
  • cerebras    DISABLED (402 Payment Required since 2026-08-19) — config RETAINED
  • gemini      DISABLED (free-tier RPM too tight for a pool) — config RETAINED

WHY THIS FILE WAS REWRITTEN (incident 2026-08-19, FEATURES_LLM_FIX.md):
The previous pool was a FLAT LIST OF KEYS that treated every exception identically
and retried 40 times. Two consequences:

  1. Groq returns `413 Request too large` for the ~9k-token Daily-CA article prompt
     (free tier ≈ 6k tokens/minute). That is DETERMINISTIC — no number of retries or
     extra keys can ever satisfy it, because a single request cannot be split across
     keys. Cerebras was silently the only provider able to serve those prompts.
  2. When Cerebras began returning `402`, its 5 dead keys were retried on EVERY call
     in EVERY job, each round burning the 15/30/60/120s cooldown ladder.

Three mechanisms fix that permanently:

  A. CAPABILITY ROUTING (_usable_entries)
     Each provider declares `max_request_tokens`. A prompt is only ever offered to a
     provider large enough to accept it. This also implements the call-type ordering:
     a small prompt sees groq first; a 9k prompt has groq filtered out and lands on
     mistral deterministically — so article style stays stable day to day.

  B. ERROR CLASSIFICATION (_classify)
     413 → SKIP_PROVIDER (no retry, escalate)   401/402/403 → DISABLE_PROVIDER (TTL)
     429/5xx/timeout → RETRY (backoff, correct)

  C. TTL'D CIRCUIT BREAKER (_mark_unhealthy)
     A dead provider is parked for 30 minutes, not for the process lifetime — the
     long-running web dyno recovers on its own, cron jobs recover on next start.

An empty/whitespace completion is treated as a FAILURE, never a success: one
OpenRouter free model was observed returning HTTP 200 with an empty body.

PUBLIC API — unchanged, no caller edits required:
    llm_call(prompt, mode="standard") -> str          ("" on permanent failure)
    llm_call_json(prompt, system_prompt, mode) -> str ("" on permanent failure)
    check_any_llm_available() -> bool
    INTER_CALL_SLEEP

Adding a provider: append one ProviderSpec below + the key in settings. Nothing else.
"""

import time
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.cache import cache

import requests
import sentry_sdk
import structlog
from cerebras.cloud.sdk import (
    Cerebras,
)  # cerebras-cloud-sdk>=1.67.0 (kept: provider disabled, not removed)
from groq import Groq
from openai import OpenAI

logger = structlog.get_logger(__name__)

# ── Rate Limit Config ─────────────────────────────────────────────────────────
# 15 s soft throttle — unchanged from the pre-incident behaviour. Daily token load
# is deliberately NOT reduced (FEATURES_LLM_FIX.md decision #9).
INTER_CALL_SLEEP = 15.0
RETRY_WAIT_TIMES = [15, 30, 60, 120]  # cooldown ladder, only for RETRY-class errors

# Circuit breaker: how long a 401/402/403 provider stays parked.
UNHEALTHY_TTL_SECONDS = 30 * 60

# OpenRouter rotates its free model line-up without notice, so the model id is
# resolved live and cached for a day.
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_MODEL_CACHE_KEY = "llm:openrouter:model"
OPENROUTER_MODEL_TTL = 24 * 3600

# Models that are $0 but unusable. Verified 2026-08-21 (FEATURES_LLM_FIX.md §5):
#   dots-3-note-preview  → HTTP 200 with an EMPTY body
#   nvidia/nemotron-*    → leak chain-of-thought into the article body
#   inkling*             → 403 "only available on agentic harnesses"
#   lyria/whisper/…      → not chat models (genuinely $0, but cannot chat)
_MODEL_DENYLIST = ("dots-3-note", "nemotron", "inkling")
_NON_CHAT_MARKERS = (
    "lyria",
    "whisper",
    "tts",
    "embed",
    "rerank",
    "image",
    "video",
    "audio",
    "sora",
    "veo",
    "imagen",
    "dall-e",
    "flux",
    "stable-diffusion",
)

# Temperature / token settings per call mode — unchanged.
_MODE_CONFIG: dict[str, dict] = {
    "writer": {"temperature": 0.25, "max_tokens": 2048},
    "critique": {"temperature": 0.10, "max_tokens": 2048},
    "standard": {"temperature": 0.10, "max_tokens": 2048},
    "quiz": {"temperature": 0.70, "max_tokens": 4000},
    "article": {"temperature": 0.70, "max_tokens": 2000},
}

# ── Error classification ──────────────────────────────────────────────────────
_RETRY = "retry"  # transient — try another key, then back off
_SKIP_PROVIDER = "skip_provider"  # this provider CANNOT serve this request, ever
_DISABLE_PROVIDER = "disable_provider"  # credentials dead — park the provider


def _classify(exc: Exception) -> str:
    """
    Map a provider exception to a recovery action.

    This is the heart of the fix. Previously every exception meant "try the next
    key", which turned a deterministic 413 into 40 guaranteed-useless attempts and
    let 5 dead Cerebras keys tax every call in the system.
    """
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    text = str(exc).lower()

    def has(code: int) -> bool:
        return status == code or f"error code: {code}" in text or f" {code} " in text

    # Payload larger than this provider's per-request / TPM allowance.
    # Deterministic: retrying the same request here can never succeed.
    if has(413) or "request too large" in text or "context length" in text:
        return _SKIP_PROVIDER

    # Credentials dead / billing required / forbidden.
    if has(401) or has(402) or has(403) or "payment required" in text:
        return _DISABLE_PROVIDER

    # Model retired or renamed — skip this provider rather than hammer it.
    if has(404) or "model not found" in text or "unavailable for free" in text:
        return _SKIP_PROVIDER

    return _RETRY


# ── Provider registry ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ProviderSpec:
    """One provider's capabilities. The registry is the single source of truth."""

    name: str
    settings_key: str  # env var NAME holding comma-separated keys
    model_setting: str  # settings attr allowing a model override
    default_model: str
    sdk: str  # "groq" | "cerebras" | "openai"
    max_request_tokens: int  # CAPABILITY GATE — the permanent 413 fix
    supports_json_mode: bool
    enabled: bool
    base_url: str | None = None


PROVIDERS: list[ProviderSpec] = [
    # Order matters: first usable provider wins. groq is first so small calls keep
    # today's exact behaviour; its low cap excludes it from large prompts automatically.
    ProviderSpec(
        name="groq",
        settings_key="GROQ_API_KEY",
        model_setting="GROQ_MODEL",
        default_model="openai/gpt-oss-120b",
        sdk="groq",
        max_request_tokens=5_500,  # free tier ≈ 6k TPM; headroom for the completion
        supports_json_mode=True,
        enabled=True,
    ),
    ProviderSpec(
        name="mistral",
        settings_key="MISTRAL_API_KEY",
        model_setting="MISTRAL_MODEL",
        default_model="mistral-medium-2508",  # L0b: 500 words in 10.3s, clean markdown
        base_url="https://api.mistral.ai/v1",
        sdk="openai",
        max_request_tokens=120_000,
        supports_json_mode=True,
        enabled=True,
    ),
    ProviderSpec(
        name="openrouter",
        settings_key="OPENROUTER_API_KEY",
        model_setting="OPENROUTER_MODEL",
        default_model="minimax/minimax-m3:free",  # seed; re-resolved daily
        base_url="https://openrouter.ai/api/v1",
        sdk="openai",
        max_request_tokens=900_000,
        supports_json_mode=True,
        enabled=True,
    ),
    # ── DISABLED — configuration deliberately RETAINED ───────────────────────
    # Cerebras served every large prompt until 2026-08-19, when all keys began
    # returning 402. Keys, SDK import and this row stay in place: restoring the
    # provider is a one-boolean change if free access ever returns.
    ProviderSpec(
        name="cerebras",
        settings_key="CEREBRAS_API_KEY",
        model_setting="CEREBRAS_MODEL",
        default_model="gpt-oss-120b",
        sdk="cerebras",
        max_request_tokens=60_000,
        supports_json_mode=True,
        enabled=False,
    ),
    # Gemini: free-tier RPM too tight for a rotating pool (project decision).
    ProviderSpec(
        name="gemini",
        settings_key="GEMINI_API_KEY",
        model_setting="GEMINI_MODEL",
        default_model="gemini-2.0-flash",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        sdk="openai",
        max_request_tokens=900_000,
        supports_json_mode=True,
        enabled=False,
    ),
]

_DISABLED_KEY_VALUES = {"", "dummy-key-for-build"}


@dataclass
class _LLMEntry:
    """One API key bound to its provider spec."""

    client: Any  # Groq | Cerebras | OpenAI — all expose .chat.completions.create()
    provider: str
    spec: ProviderSpec


# ── Circuit breaker (TTL'd, never permanent) ──────────────────────────────────
# Django's cache is Redis-backed in this project, so the breaker is shared across
# Render workers. It degrades to a per-process dict if the cache is unavailable
# (e.g. the lean scraper environment), which is still better than no breaker.
_local_unhealthy: dict[str, float] = {}


def _unhealthy_key(provider: str) -> str:
    return f"llm:unhealthy:{provider}"


def _mark_unhealthy(provider: str, reason: str) -> None:
    try:
        cache.set(_unhealthy_key(provider), reason, UNHEALTHY_TTL_SECONDS)
    except Exception:
        _local_unhealthy[provider] = time.time() + UNHEALTHY_TTL_SECONDS
    logger.warning(
        "llm_provider_parked",
        provider=provider,
        ttl_seconds=UNHEALTHY_TTL_SECONDS,
        reason=reason[:120],
    )


def _is_unhealthy(provider: str) -> bool:
    try:
        if cache.get(_unhealthy_key(provider)) is not None:
            return True
    except Exception:
        pass
    until = _local_unhealthy.get(provider)
    return until is not None and until > time.time()


# ── OpenRouter dynamic model resolution ───────────────────────────────────────


def _is_usable_model_id(model_id: str) -> bool:
    low = model_id.lower()
    return not any(bad in low for bad in _MODEL_DENYLIST + _NON_CHAT_MARKERS)


def _resolve_openrouter_model(default: str) -> str:
    """
    Return a currently-free OpenRouter chat model, cached for 24 h.

    OpenRouter retires free models without notice — every id hardcoded at design
    time had already moved to paid within days. Sorting by context length alone is
    NOT enough: the 2nd–4th ranked models were found to leak chain-of-thought or
    return an empty body, hence the denylist.

    Order of preference: cache → settings override → live list → the pinned default.
    Never raises.
    """
    override = (getattr(settings, "OPENROUTER_MODEL", "") or "").strip()
    if override:
        return override

    try:
        cached = cache.get(OPENROUTER_MODEL_CACHE_KEY)
        if cached:
            return str(cached)
    except Exception:
        pass

    try:
        resp = requests.get(OPENROUTER_MODELS_URL, timeout=15)
        resp.raise_for_status()
        rows = resp.json().get("data", [])
    except Exception as exc:
        logger.warning("openrouter_model_list_failed", error=str(exc)[:120])
        return default

    free: list[tuple[int, str]] = []
    for row in rows:
        model_id = row.get("id") or ""
        pricing = row.get("pricing") or {}
        if not model_id or not _is_usable_model_id(model_id):
            continue
        try:
            if (
                float(pricing.get("prompt", 1)) == 0.0
                and float(pricing.get("completion", 1)) == 0.0
            ):
                free.append((int(row.get("context_length") or 0), model_id))
        except (TypeError, ValueError):
            continue

    free.sort(reverse=True)
    chosen = default
    for _ctx, model_id in free[:5]:
        chosen = model_id
        break

    try:
        cache.set(OPENROUTER_MODEL_CACHE_KEY, chosen, OPENROUTER_MODEL_TTL)
    except Exception:
        pass
    logger.info("openrouter_model_resolved", model=chosen, free_candidates=len(free))
    return chosen


def _model_for(spec: ProviderSpec) -> str:
    """Model id for this provider — env override, dynamic resolution, or default."""
    configured = (getattr(settings, spec.model_setting, "") or "").strip()
    if spec.name == "openrouter":
        return _resolve_openrouter_model(configured or spec.default_model)
    return configured or spec.default_model


# ── Pool Builder ──────────────────────────────────────────────────────────────


def _build_client(spec: ProviderSpec, key: str) -> Any:
    if spec.sdk == "groq":
        return Groq(api_key=key)
    if spec.sdk == "cerebras":
        return Cerebras(api_key=key)
    return OpenAI(api_key=key, base_url=spec.base_url)


def _build_pool() -> list[_LLMEntry]:
    """
    Build the flat key pool from the registry. Providers with `enabled=False` or no
    configured key are skipped silently — a missing key must never crash boot.
    """
    pool: list[_LLMEntry] = []

    for spec in PROVIDERS:
        if not spec.enabled:
            continue
        raw = getattr(settings, spec.settings_key, "") or ""
        for key in [k.strip() for k in raw.split(",") if k.strip()]:
            if key in _DISABLED_KEY_VALUES:
                continue
            try:
                pool.append(
                    _LLMEntry(
                        client=_build_client(spec, key),
                        provider=spec.name,
                        spec=spec,
                    )
                )
            except Exception as exc:  # a broken SDK must not kill the others
                logger.warning(
                    "llm_client_init_failed", provider=spec.name, error=str(exc)[:120]
                )

    if not pool:
        logger.error("llm_pool_empty", message="No LLM API keys found in settings!")
        groq_spec = PROVIDERS[0]
        pool.append(
            _LLMEntry(
                client=Groq(api_key="DUMMY_KEY"),
                provider=groq_spec.name,
                spec=groq_spec,
            )
        )
        return pool

    summary: dict[str, int] = {}
    for entry in pool:
        summary[entry.provider] = summary.get(entry.provider, 0) + 1
    logger.info("llm_pool_initialized", total=len(pool), providers=summary)
    return pool


_pool: list[_LLMEntry] = _build_pool()
_pool_size: int = len(_pool)
_current_key_idx: int = 0


# ── Routing ───────────────────────────────────────────────────────────────────


def _estimate_tokens(text: str) -> int:
    """~4 chars per token. Deliberately rough — it only has to pick a provider."""
    return len(text) // 4


def _usable_entries(est_tokens: int, needs_json: bool) -> list[_LLMEntry]:
    """
    Providers that can actually serve this request, in registry order.

    Filtering on `max_request_tokens` is what permanently prevents the 413: a 9k
    prompt is simply never offered to a ~6k-capacity provider. It also produces the
    intended ordering for free — small prompts see groq first, large prompts land
    deterministically on mistral.
    """
    usable = [
        e
        for e in _pool
        if e.spec.max_request_tokens >= est_tokens
        and (e.spec.supports_json_mode or not needs_json)
        and not _is_unhealthy(e.provider)
    ]
    if not usable:
        logger.error(
            "llm_no_capable_provider",
            est_tokens=est_tokens,
            needs_json=needs_json,
            pool_size=_pool_size,
        )
    return usable


def _dispatch(
    messages: list[dict],
    cfg: dict,
    log_name: str,
    json_mode: bool,
    est_tokens: int,
) -> str:
    """
    Try every capable provider/key until one returns a non-empty completion.

    Rounds exist only for RETRY-class errors (429 / 5xx). A 413 removes the provider
    from this request immediately, and a 402 parks it for everyone — neither ever
    reaches the cooldown ladder, which is what made the old pool so slow.
    """
    global _current_key_idx

    skipped: set[str] = set()
    last_error = ""

    for round_idx, wait in enumerate([0] + RETRY_WAIT_TIMES):
        if wait:
            logger.warning("llm_all_keys_exhausted", cooldown_seconds=wait)
            time.sleep(wait)

        entries = [
            e
            for e in _usable_entries(est_tokens, json_mode)
            if e.provider not in skipped
        ]
        if not entries:
            break

        retryable_seen = False

        for offset in range(len(entries)):
            entry = entries[(_current_key_idx + offset) % len(entries)]
            if entry.provider in skipped or _is_unhealthy(entry.provider):
                continue

            model = _model_for(entry.spec)
            kwargs: dict = {
                "model": model,
                "messages": messages,
                "temperature": cfg["temperature"],
                "max_tokens": cfg["max_tokens"],
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            try:
                response = entry.client.chat.completions.create(**kwargs)
                content = (response.choices[0].message.content or "").strip()

                # An empty body is a FAILURE, not a success. One free OpenRouter
                # model returns HTTP 200 with nothing in it; treating that as valid
                # is exactly how a silent outage starts.
                if not content:
                    logger.warning(
                        "llm_empty_response", provider=entry.provider, model=model
                    )
                    retryable_seen = True
                    continue

                logger.info(
                    f"{log_name}_success",
                    chars=len(content),
                    provider=entry.provider,
                    model=model,
                    est_tokens=est_tokens,
                )
                _current_key_idx = (_current_key_idx + offset + 1) % max(
                    len(entries), 1
                )
                return content

            except Exception as exc:
                action = _classify(exc)
                last_error = str(exc).replace("\n", " ")[:160]
                logger.warning(
                    f"{log_name}_failed",
                    provider=entry.provider,
                    model=model,
                    action=action,
                    round=round_idx,
                    error=last_error[:110],
                )

                if action == _SKIP_PROVIDER:
                    skipped.add(entry.provider)
                elif action == _DISABLE_PROVIDER:
                    _mark_unhealthy(entry.provider, last_error)
                    skipped.add(entry.provider)
                else:
                    retryable_seen = True

        # Nothing transient left to wait for — backing off would only waste time.
        if not retryable_seen:
            break

    logger.error(
        "llm_permanently_failed",
        pool_size=_pool_size,
        est_tokens=est_tokens,
        skipped=sorted(skipped),
        last_error=last_error[:160],
    )
    sentry_sdk.capture_message(
        f"LLM permanently failed ({log_name}): est_tokens={est_tokens}, "
        f"skipped={sorted(skipped)}, last_error={last_error[:160]}",
        level="error",
    )
    return ""


# ── Core Call Wrappers ────────────────────────────────────────────────────────


def llm_call(prompt: str, mode: str = "standard") -> str:
    """
    One LLM call through the multi-provider pool.

    Args:
        prompt: full prompt string.
        mode:   'standard' | 'writer' | 'critique' | 'quiz' | 'article'

    Returns:
        Response string. Empty string on permanent failure (every capable provider
        exhausted) — callers treat "" as a failed cycle.
    """
    time.sleep(INTER_CALL_SLEEP)
    cfg = _MODE_CONFIG.get(mode, _MODE_CONFIG["standard"])
    return _dispatch(
        messages=[{"role": "user", "content": prompt}],
        cfg=cfg,
        log_name="llm_call",
        json_mode=False,
        est_tokens=_estimate_tokens(prompt),
    )


def llm_call_json(
    prompt: str,
    system_prompt: str = "",
    mode: str = "standard",
) -> str:
    """
    Like llm_call() but passes a system message and requests JSON output.

    Only providers declaring `supports_json_mode` are considered, so a provider that
    rejects `response_format` can never break a structured-output caller.

    Returns:
        Raw JSON string (caller does json.loads). Empty string on permanent failure.
    """
    time.sleep(INTER_CALL_SLEEP)
    cfg = _MODE_CONFIG.get(mode, _MODE_CONFIG["standard"])

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    return _dispatch(
        messages=messages,
        cfg=cfg,
        log_name="llm_call_json",
        json_mode=True,
        est_tokens=_estimate_tokens(system_prompt + prompt),
    )


def check_any_llm_available() -> bool:
    """
    Fast pre-flight / mid-run circuit breaker.

    Tries one minimal call per ENABLED provider (not per key — a dead provider is
    dead on every key, and the old per-key sweep was itself part of the 402 tax).
    Returns True on the first provider that answers.

    No sleep, no retry ladder — intentionally fast so the caller can decide whether
    to continue or abort without burning quota.
    Called by: ingestor_service.py and the generate_book_content command.
    """
    seen: set[str] = set()

    for entry in _pool:
        if entry.provider in seen or _is_unhealthy(entry.provider):
            continue
        seen.add(entry.provider)

        try:
            response = entry.client.chat.completions.create(
                model=_model_for(entry.spec),
                messages=[{"role": "user", "content": "Reply: OK"}],
                max_tokens=3,
                temperature=0,
            )
            if (response.choices[0].message.content or "").strip():
                logger.info("llm_health_ok", provider=entry.provider)
                return True
            logger.warning("llm_health_empty", provider=entry.provider)
        except Exception as exc:
            action = _classify(exc)
            if action == _DISABLE_PROVIDER:
                _mark_unhealthy(entry.provider, str(exc))
            logger.warning(
                "llm_health_provider_failed",
                provider=entry.provider,
                action=action,
                error=str(exc)[:110],
            )

    logger.error("llm_health_all_failed", pool_size=_pool_size, providers=sorted(seen))
    return False
