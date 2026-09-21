"""
engines/book_content/services/llm_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Unified multi-provider LLM client — shared by every engine except research_agent
(which has its own isolated pool at research_agent/llmops/groq_client.py).

PROVIDER REGISTRY (see PROVIDERS below — the single source of truth):
  • groq        openai/gpt-oss-120b     7.5k est-token cap  primary (incl. the CA article)
  • mistral     mistral-medium-2508      ~120k cap          large calls beyond the gate
  • openrouter  minimax/minimax-m3:free  ~900k cap          emergency fallback

L10/L11 (FEATURES_LLM_FIX.md Part II, 2026-09-20): the Daily-CA article prompt was
shrunk to fit Groq (its 27k-char instruction template was 78 % of the prompt), the
Groq gate was raised to what a live call proved (≥ 10,889 tokens per request), and
the article got its own `ca_article` mode (4,000-token completion, low reasoning
effort) because gpt-oss-120b spent 1,126 of a 2,048-token budget reasoning and cut
the article short. Between 2026-09-18 and 09-20 the article body had depended on
Mistral (quota-dead) and OpenRouter's daily free-model pick, which broke.
  • gemini      DISABLED (free-tier RPM too tight for a pool) — config RETAINED
  • cerebras    REMOVED 2026-09-16 — 402 Payment Required on every key since
                2026-08-19, and its module-level SDK import crashed every lean
                environment without the package (the CA scraper, twice). If free
                access ever returns it comes back as a new ProviderSpec + the SDK
                in requirements, not by resurrecting the old row.

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

  D. OPENROUTER MODELS EARN ADOPTION (L11b, 2026-09-20 — _resolve_openrouter_model)
     A resolved free model is smoke-tested before it is cached; one that answers
     with an empty body or a 404 is demoted for a day and the next candidate is
     tried within the same call (demote_openrouter_model, capped per call).

  E. PER-KEY PARK ON THE PROVIDER'S OWN CLOCK (L15, Part III 2026-09-21 —
     _limit_class / _retry_hint_seconds / _mark_rate_limited)
     Groq meters the free tier PER ORGANISATION PER MODEL on a ROLLING 24 h
     window (200k tokens/day for gpt-oss-120b), and the five Groq keys are five
     accounts, i.e. five separate buckets. A 429 is read, not counted: a daily-class
     message ("tokens per day (TPD) … try again in 47m") parks THAT KEY for the time
     the provider names; a per-minute one ("… try again in 2.5s") makes the round
     wait that hint instead of the 15/30/60/120 s ladder; anything else is retried
     as before. With every key parked a call returns "" at once — no ladder — and
     `pool_exhausted()` lets a cron stop cleanly instead of grinding every item
     through four and a half minutes of retries (the 2026-09-21 shape).

An empty/whitespace completion is treated as a FAILURE, never a success: one
OpenRouter free model was observed returning HTTP 200 with an empty body.

PUBLIC API — unchanged, no caller edits required:
    llm_call(prompt, mode="standard") -> str          ("" on permanent failure)
    llm_call_json(prompt, system_prompt, mode) -> str ("" on permanent failure)
    check_any_llm_available() -> bool
    pool_exhausted() -> bool                          (every key parked right now)
    INTER_CALL_SLEEP

Adding a provider: append one ProviderSpec below + the key in settings. Nothing else.
"""

import re
import threading
import time
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.cache import cache

import requests
import sentry_sdk
import structlog
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

# L11b (2026-09-20). A resolved model is adopted only after a one-shot smoke call,
# and a model that answers with an empty body or a 404 is DEMOTED for a day — the
# cached pick is cleared and the next candidate is tried within the same call. On
# 2026-09-18 the blind pick landed on a model returning HTTP 200 with nothing in
# it; every key retried it, every round retried it, every article retried it
# (~15 minutes each), and the cache served the same dead id all day. Two days
# later the id went paid-only (404) and the cache still held it.
OPENROUTER_BAD_MODEL_TTL = 24 * 3600
OPENROUTER_MAX_DEMOTIONS_PER_CALL = 2
OPENROUTER_MAX_CANDIDATES = 5
# The free tier's "free-models-per-day" quota is per ACCOUNT and resets daily;
# once the smoke call sees it, no candidate can pass — park the provider instead
# of burning five more calls per resolution (first live run, 2026-09-20).
OPENROUTER_QUOTA_PARK_SECONDS = 60 * 60

# L15 (Part III, 2026-09-21). A key that answers a DAILY-class 429 is parked at
# once, for as long as the provider says ("Please try again in 47m3.2s"), clamped:
# never under five minutes — Groq's rolling 24 h window returns a few thousand
# tokens at a time, and polling it faster only burns requests — and never over six
# hours, so a cron always recovers within its own day. The L11c streak counter
# ("three rounds of 429s") is gone: it parked a healthy provider on per-minute
# bursts on 2026-09-20 and, on 2026-09-21, let five empty daily buckets sit in
# the 15/30/60/120 s ladder for three rounds before it noticed.
RATE_LIMIT_PARK_SECONDS = 5 * 60  # default / floor
KEY_PARK_MAX_SECONDS = 6 * 3600
# Mistral's "Rate limit exceeded … code 1300" has been every reply from that tier
# since 2026-09-18 and carries no hint. A quarter-hour park saves ~4 s per retry
# round on every call while the keys are configured at all.
MISTRAL_1300_PARK_SECONDS = 15 * 60
# A per-minute 429 that names a wait no longer than this replaces the ladder step.
HINT_WAIT_MAX_SECONDS = 60.0

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

# Temperature / token settings per call mode.
#
# `ca_article` (L11, 2026-09-20) is the Daily-CA article's own mode. Measured on real
# prompts: at max_tokens 2,048 gpt-oss-120b used 1,126 tokens on reasoning and
# returned a 615-word stub with no closing lines (`finish_reason=length`), so the
# completion budget is 4,000. Effort was A/B'd on the same three proposals with the
# rewritten prompt: "low" gave 0 / 3 / 8 concept links and 5–9 numbers per article
# that traced to nothing in the sources; "medium" gave 8 / 6 / 6 links, 633–751
# words and 0–3 untraceable numbers — it follows the rules, "low" rationalises
# around them. ~1,100 reasoning + ~1,000 article tokens still sit well inside 4,000.
# `reasoning_effort` is only sent to Groq, and only for its reasoning models — see
# _dispatch. The shared `writer` mode (book sections, overviews, planner) is left
# exactly as it was: one root cause at a time.
_MODE_CONFIG: dict[str, dict] = {
    "writer": {"temperature": 0.25, "max_tokens": 2048},
    "critique": {"temperature": 0.10, "max_tokens": 2048},
    "standard": {"temperature": 0.10, "max_tokens": 2048},
    "quiz": {"temperature": 0.70, "max_tokens": 4000},
    "article": {"temperature": 0.70, "max_tokens": 2000},
    "ca_article": {
        "temperature": 0.25,
        "max_tokens": 4000,
        "reasoning_effort": "medium",
    },
}

# Groq models that accept `reasoning_effort`. Sending it to any other model is a
# 400, so the marker list is the gate, not the provider name alone.
_REASONING_MODEL_MARKERS = ("gpt-oss", "qwen3")


def _reasoning_kwargs(provider: str, model: str, cfg: dict) -> dict:
    """`extra_body` for a Groq reasoning model when the mode asks for an effort level."""
    effort = cfg.get("reasoning_effort")
    if not effort or provider != "groq":
        return {}
    if not any(marker in model.lower() for marker in _REASONING_MODEL_MARKERS):
        return {}
    return {"extra_body": {"reasoning_effort": effort}}


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


def _classify_is_404(exc: Exception) -> bool:
    """A retired / paid-only MODEL (not an oversized request) — demotable."""
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    text = str(exc).lower()
    return (
        status == 404
        or "error code: 404" in text
        or "model not found" in text
        or "unavailable for free" in text
    )


def _is_429(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    text = str(exc).lower()
    return status == 429 or "error code: 429" in text or "rate limit" in text


# ── 429 anatomy (L15) ─────────────────────────────────────────────────────────
# A 429 is read, never just counted. The class decides the reaction:
#   tpd / rpd / quota  → a DAILY or account allowance — park the key for the time
#                        the provider names (Groq "tokens per day (TPD) … try again
#                        in 47m3.2s", OpenRouter "free-models-per-day", any
#                        credits / quota / monthly wording)
#   tpm / rpm          → a per-minute burst — retry; the round waits the hint
#                        ("try again in 2.5s") instead of the ladder step
#   mistral_1300       → Mistral's bare "Rate limit exceeded … code 1300", the only
#                        reply from that tier since 2026-09-18 — park the provider
#   other              → retry ladder, unchanged
# Counting was the 2026-09-20 mistake (three rounds of per-minute 429s parked the
# only working provider); trusting the message is what the first Part III log
# lacked — our own truncation hid whether a 429 was TPM or TPD.
_LIMIT_TPM = "tpm"
_LIMIT_RPM = "rpm"
_LIMIT_TPD = "tpd"
_LIMIT_RPD = "rpd"
_LIMIT_QUOTA = "quota"
_LIMIT_MISTRAL_1300 = "mistral_1300"
_LIMIT_OTHER = "other"
_DAILY_LIMIT_CLASSES = frozenset({_LIMIT_TPD, _LIMIT_RPD, _LIMIT_QUOTA})
_PER_MINUTE_LIMIT_CLASSES = frozenset({_LIMIT_TPM, _LIMIT_RPM})
_QUOTA_429_MARKERS = ("per day", "per-day", "daily", "quota", "credits", "monthly")

# Groq: "Please try again in 1h2m3.5s" / "1m19.968s" / "2.5s" / "320ms".
_RETRY_HINT_RE = re.compile(r"try again in\s+([0-9hms.]+)", re.IGNORECASE)
_DURATION_PART_RE = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")
_DURATION_UNIT_SECONDS = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}


def _limit_class(exc: Exception) -> str:
    """Which allowance a 429 names — '' when the error is not a 429 at all."""
    if not _is_429(exc):
        return ""
    text = str(exc).lower()
    if "tokens per day" in text or "(tpd)" in text:
        return _LIMIT_TPD
    if "requests per day" in text or "(rpd)" in text:
        return _LIMIT_RPD
    if "tokens per minute" in text or "(tpm)" in text:
        return _LIMIT_TPM
    if "requests per minute" in text or "(rpm)" in text:
        return _LIMIT_RPM
    if "'code': '1300'" in text or '"code": "1300"' in text:
        return _LIMIT_MISTRAL_1300
    if any(marker in text for marker in _QUOTA_429_MARKERS):
        return _LIMIT_QUOTA
    return _LIMIT_OTHER


def _is_quota_429(exc: Exception) -> bool:
    """A 429 naming a daily / account allowance — the only kind that parks a key."""
    return _limit_class(exc) in _DAILY_LIMIT_CLASSES


def _retry_hint_seconds(exc: Exception) -> float | None:
    """
    How long the provider itself says to wait, in seconds — None when it does not
    say. Groq puts it in the message; an OpenAI-compatible provider may send a
    `Retry-After` header instead, read when the SDK exposes the response.
    """
    match = _RETRY_HINT_RE.search(str(exc))
    if match:
        parts = _DURATION_PART_RE.findall(match.group(1))
        if parts:
            return sum(
                float(value) * _DURATION_UNIT_SECONDS[unit] for value, unit in parts
            )
    try:
        header = exc.response.headers.get("retry-after")  # type: ignore[attr-defined]
        if header:
            return float(header)
    except Exception:
        pass
    return None


# ── Provider registry ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ProviderSpec:
    """One provider's capabilities. The registry is the single source of truth."""

    name: str
    settings_key: str  # env var NAME holding comma-separated keys
    model_setting: str  # settings attr allowing a model override
    default_model: str
    sdk: str  # "groq" | "openai" (OpenAI-compatible: mistral, openrouter, gemini)
    max_request_tokens: int  # CAPABILITY GATE — the permanent 413 fix
    supports_json_mode: bool
    enabled: bool
    base_url: str | None = None


PROVIDERS: list[ProviderSpec] = [
    # Order matters: first usable provider wins. groq is first so small calls keep
    # today's exact behaviour; its cap excludes it from oversized prompts automatically.
    ProviderSpec(
        name="groq",
        settings_key="GROQ_API_KEY",
        model_setting="GROQ_MODEL",
        default_model="openai/gpt-oss-120b",
        sdk="groq",
        # Estimated tokens (len/4). Raised 5,500 → 7,500 on 2026-09-20 (L11a) from a
        # live measurement, not a guess: a 6,889-real-token prompt with max_tokens
        # 4,000 (10,889 requested) was accepted; real tokens run 0.873 × estimate, so
        # 7,500 est. → 6,548 real + 4,000 = 10,548 < 10,889. Never raise it past
        # (proven TPM − largest mode max_tokens) ÷ 0.873; the 413 returns if you do.
        max_request_tokens=7_500,
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
    # (Cerebras used to sit here, disabled. Removed 2026-09-16 — see the module
    # docstring. A disabled row still needs its SDK importable, which is what
    # broke the lean scraper environment.)
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

    client: Any  # Groq | OpenAI — both expose .chat.completions.create()
    provider: str
    spec: ProviderSpec
    # Position among this provider's keys — the unit a daily-class 429 parks.
    # For Groq each key is its own account, hence its own daily bucket (L15).
    key_idx: int = 0


# ── Circuit breaker (TTL'd, never permanent) ──────────────────────────────────
# Django's cache is Redis-backed in this project, so the breaker is shared across
# Render workers. It degrades to a per-process dict if the cache is unavailable
# (e.g. the lean scraper environment), which is still better than no breaker.
_local_unhealthy: dict[str, float] = {}

# ── Which provider actually served the last call ─────────────────────────────
# The pool chooses a provider at call time, so a caller has no way to know who
# answered. Without this, a change in output quality or length is undiagnosable
# after the fact — exactly the dead end hit on 2026-09-02 when Daily CA article
# length fell 937 → 603 words with the RAG input held flat.
#
# Thread-local, not a module global: gunicorn runs 8 threads alongside
# process_tasks, so concurrent generations would otherwise overwrite each
# other's record.
_last_call = threading.local()


def last_call_provider() -> str:
    """Provider that served this thread's most recent successful call ('' if none)."""
    return getattr(_last_call, "provider", "")


def last_call_model() -> str:
    """Model id that served this thread's most recent successful call ('' if none)."""
    return getattr(_last_call, "model", "")


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


# ── Rate-limit park (L11c → L15) ─────────────────────────────────────────────
# Two levels. A PROVIDER park (`llm:ratelimited:<provider>`) is for an allowance
# shared by every key of that provider — OpenRouter's per-account daily quota seen
# by the smoke call. A KEY park (`llm:ratelimited:<provider>:<idx>`) is what a
# daily-class 429 on the generation path sets: the five Groq keys are five
# accounts, i.e. five separate buckets, so one empty bucket must neither silence
# the other four nor keep hammering itself. Both levels are checked on routing.
# Keyed by the cache key so the local fallback dict mirrors the cache exactly.
_local_rate_limited: dict[str, float] = {}


def _rate_limited_key(provider: str, key_idx: int | None = None) -> str:
    if key_idx is None:
        return f"llm:ratelimited:{provider}"
    return f"llm:ratelimited:{provider}:{key_idx}"


def _mark_rate_limited(
    provider: str,
    ttl_seconds: float = RATE_LIMIT_PARK_SECONDS,
    reason: str = "429",
    key_idx: int | None = None,
    limit: str = "",
) -> None:
    ttl = int(round(ttl_seconds))
    cache_key = _rate_limited_key(provider, key_idx)
    try:
        cache.set(cache_key, reason[:120], ttl)
    except Exception:
        _local_rate_limited[cache_key] = time.time() + ttl
    logger.warning(
        "llm_key_parked" if key_idx is not None else "llm_provider_rate_limit_parked",
        provider=provider,
        key=key_idx,
        limit=limit,
        ttl_seconds=ttl,
        reason=reason[:120],
    )


def _is_rate_limited(provider: str, key_idx: int | None = None) -> bool:
    """Parked at the provider level, or — when a key is named — at the key level."""
    cache_keys = [_rate_limited_key(provider)]
    if key_idx is not None:
        cache_keys.append(_rate_limited_key(provider, key_idx))
    for cache_key in cache_keys:
        try:
            if cache.get(cache_key) is not None:
                return True
        except Exception:
            pass
        until = _local_rate_limited.get(cache_key)
        if until is not None and until > time.time():
            return True
    return False


def _park_seconds_for(exc: Exception, provider: str) -> float:
    """
    How long a daily-class 429 parks a key: the provider's own hint, clamped to
    [5 min, 6 h]. Without a hint OpenRouter's daily quota keeps its hour (the
    smoke-call figure); anything else gets the five-minute floor.
    """
    hint = _retry_hint_seconds(exc)
    if hint is None:
        if provider == "openrouter":
            return float(OPENROUTER_QUOTA_PARK_SECONDS)
        return float(RATE_LIMIT_PARK_SECONDS)
    return min(max(hint, float(RATE_LIMIT_PARK_SECONDS)), float(KEY_PARK_MAX_SECONDS))


# ── OpenRouter dynamic model resolution ───────────────────────────────────────
_local_demoted: dict[str, float] = {}


def _is_usable_model_id(model_id: str) -> bool:
    low = model_id.lower()
    return not any(bad in low for bad in _MODEL_DENYLIST + _NON_CHAT_MARKERS)


def _demoted_key(model_id: str) -> str:
    return f"llm:openrouter:bad:{model_id}"


def _is_demoted(model_id: str) -> bool:
    try:
        if cache.get(_demoted_key(model_id)) is not None:
            return True
    except Exception:
        pass
    until = _local_demoted.get(model_id)
    return until is not None and until > time.time()


def demote_openrouter_model(model_id: str, reason: str) -> None:
    """
    Park a free model for a day and forget the cached pick, so the next OpenRouter
    entry re-resolves to a different candidate. Never raises.
    """
    try:
        cache.set(_demoted_key(model_id), reason[:120], OPENROUTER_BAD_MODEL_TTL)
        cache.delete(OPENROUTER_MODEL_CACHE_KEY)
    except Exception:
        _local_demoted[model_id] = time.time() + OPENROUTER_BAD_MODEL_TTL
    logger.warning(
        "openrouter_model_demoted",
        model=model_id,
        ttl_seconds=OPENROUTER_BAD_MODEL_TTL,
        reason=reason[:120],
    )


_SMOKE_OK = "ok"
_SMOKE_BAD_MODEL = "bad_model"
_SMOKE_QUOTA = "quota"


def _smoke_test(client: Any, model_id: str) -> str:
    """
    One tiny call. A model that cannot say OK is not adopted (§4.7 item 3).

    Three verdicts, because the first live run (2026-09-20) showed the difference
    matters: a 429 "free-models-per-day" is the ACCOUNT's daily free quota, not the
    model — every candidate would fail the same way, and demoting ten healthy
    models for a day because the quota was spent would be wrong twice over.
    """
    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": "Reply: OK"}],
            max_tokens=_HEALTH_MAX_TOKENS,
            temperature=0,
        )
    except Exception as exc:
        verdict = _SMOKE_QUOTA if _is_429(exc) else _SMOKE_BAD_MODEL
        logger.warning(
            "openrouter_smoke_failed",
            model=model_id,
            verdict=verdict,
            error=str(exc)[:110],
        )
        return verdict
    if (response.choices[0].message.content or "").strip():
        return _SMOKE_OK
    logger.warning("openrouter_smoke_failed", model=model_id, verdict="empty body")
    return _SMOKE_BAD_MODEL


def _free_openrouter_candidates() -> list[str]:
    """Currently-$0 chat models from the live list, best context first. Never raises."""
    try:
        resp = requests.get(OPENROUTER_MODELS_URL, timeout=15)
        resp.raise_for_status()
        rows = resp.json().get("data", [])
    except Exception as exc:
        logger.warning("openrouter_model_list_failed", error=str(exc)[:120])
        return []

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
    return [model_id for _ctx, model_id in free]


def _resolve_openrouter_model(default: str, client: Any = None) -> str:
    """
    Return a currently-free OpenRouter chat model, cached for 24 h.

    OpenRouter retires free models without notice — every id hardcoded at design
    time had already moved to paid within days. Sorting by context length alone is
    NOT enough: the 2nd–4th ranked models were found to leak chain-of-thought or
    return an empty body, hence the denylist — and, since 2026-09-18, the smoke
    call and the demotion list: a candidate is adopted only after it has answered
    a one-token question, and a model that later returns nothing or a 404 is
    skipped for a day.

    Order of preference: settings override → cache → live list (smoke-tested,
    demoted ids skipped) → the pinned default (only when the list is unreachable and
    the default is not itself demoted). Returns "" when nothing is usable right
    now — the caller skips the provider for that call. Never raises, never caches
    a model that did not pass.
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

    listed = _free_openrouter_candidates()
    if not listed:
        # List unreachable: the seed default, WITHOUT caching, unless it is known
        # dead (the seed went paid-only on 2026-09-20 and was demoted twice).
        return "" if _is_demoted(default) else default

    candidates = [m for m in listed if not _is_demoted(m)]
    tried = 0
    for model_id in candidates[:OPENROUTER_MAX_CANDIDATES]:
        tried += 1
        verdict = _SMOKE_OK if client is None else _smoke_test(client, model_id)
        if verdict == _SMOKE_QUOTA:
            # The account's free daily quota is spent — no candidate can pass
            # today. Park the provider for an hour and leave the models alone.
            _mark_rate_limited(
                "openrouter",
                OPENROUTER_QUOTA_PARK_SECONDS,
                "free-models-per-day quota exhausted",
            )
            return ""
        if verdict == _SMOKE_BAD_MODEL:
            demote_openrouter_model(model_id, "failed the adoption smoke call")
            continue
        try:
            cache.set(OPENROUTER_MODEL_CACHE_KEY, model_id, OPENROUTER_MODEL_TTL)
        except Exception:
            pass
        logger.info(
            "openrouter_model_resolved",
            model=model_id,
            free_candidates=len(candidates),
            smoke_tested=tried,
        )
        return model_id

    # Nothing passed (or everything is demoted): skip the provider for this call.
    # The seed default is NOT a fallback here — the first live run cached it after
    # five failed smoke calls, then hit its 404 twice in one call.
    logger.warning(
        "openrouter_no_usable_model",
        free_candidates=len(candidates),
        listed=len(listed),
        smoke_tested=tried,
    )
    return ""


def _model_for(spec: ProviderSpec, client: Any = None) -> str:
    """Model id for this provider — env override, dynamic resolution, or default."""
    configured = (getattr(settings, spec.model_setting, "") or "").strip()
    if spec.name == "openrouter":
        return _resolve_openrouter_model(configured or spec.default_model, client)
    return configured or spec.default_model


# ── Pool Builder ──────────────────────────────────────────────────────────────


def _build_client(spec: ProviderSpec, key: str) -> Any:
    if spec.sdk == "groq":
        return Groq(api_key=key)
    return OpenAI(api_key=key, base_url=spec.base_url)


def _build_pool() -> list[_LLMEntry]:
    """
    Build the flat key pool from the registry. Providers with `enabled=False` or no
    configured key are skipped silently — a missing key must never crash boot.
    """
    pool: list[_LLMEntry] = []
    per_provider: dict[str, int] = {}

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
                        key_idx=per_provider.get(spec.name, 0),
                    )
                )
                per_provider[spec.name] = per_provider.get(spec.name, 0) + 1
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
    deterministically on mistral. A key parked by a daily-class 429 (L15) is
    filtered here too, so a spent bucket is never offered a request.
    """
    usable = [
        e
        for e in _pool
        if e.spec.max_request_tokens >= est_tokens
        and (e.spec.supports_json_mode or not needs_json)
        and not _is_unhealthy(e.provider)
        and not _is_rate_limited(e.provider, e.key_idx)
    ]
    if not usable:
        logger.error(
            "llm_no_capable_provider",
            est_tokens=est_tokens,
            needs_json=needs_json,
            pool_size=_pool_size,
            exhausted=pool_exhausted(),
        )
    return usable


def pool_exhausted() -> bool:
    """
    True when no key in the pool may be called right now — every key parked by a
    daily-class 429 or its provider disabled. No network, cache reads only.

    A cron checks this between items: once the day's buckets are spent, every
    further `llm_call` would return "" and the run should stop with a summary
    instead of walking its whole queue (Part III, 2026-09-21: static content
    4 h+, overviews 31 min, all of it retries against empty buckets).
    """
    return not any(
        not _is_unhealthy(e.provider) and not _is_rate_limited(e.provider, e.key_idx)
        for e in _pool
    )


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

    ORDER (L11d, 2026-09-20): the first capable provider in registry order is the
    PRIMARY for this call, and the key rotation happens only among ITS keys. The
    old rotation walked the whole flat key list, so with 5 Groq + 2 Mistral + 3
    OpenRouter keys roughly a third of every call type — the Daily-CA article
    included — *started* on a fallback provider and was written by whichever free
    model happened to answer. Mistral and OpenRouter are reached only when every
    Groq key has failed. The five Groq keys are five accounts — five separate
    daily buckets on a rolling 24 h window — so the rotation spreads the day's
    load across them (corrected 2026-09-21; #30 had called it one shared quota).

    429s (L15, 2026-09-21): read, not counted. A daily-class 429 parks that KEY
    for the time the provider names and the call moves on to the next key at
    once; a per-minute 429 makes the round wait the provider's hint instead of
    the ladder step. A round with nothing left to try ends the call immediately —
    no sleep — so with every key parked a call costs milliseconds, not the
    4.5 minutes that turned a 3-minute cron into a 31-minute one.
    """
    global _current_key_idx

    skipped: set[str] = set()
    last_error = ""
    demotions = 0  # L11b: OpenRouter models dropped within THIS call (capped)
    wait = 0.0  # seconds to sleep before the NEXT round, decided by this round

    def _drop_openrouter_model(model_id: str, reason: str) -> None:
        """Demote the model (up to the cap) so the next entry re-resolves; then skip."""
        nonlocal demotions
        if demotions < OPENROUTER_MAX_DEMOTIONS_PER_CALL:
            demotions += 1
            demote_openrouter_model(model_id, reason)
        else:
            skipped.add("openrouter")

    for round_idx in range(1 + len(RETRY_WAIT_TIMES)):
        entries = [
            e
            for e in _usable_entries(est_tokens, json_mode)
            if e.provider not in skipped
        ]
        if not entries:
            # Nothing usable — waiting could not change that. Return now.
            break
        if wait:
            logger.warning("llm_all_keys_exhausted", cooldown_seconds=wait)
            time.sleep(wait)

        retryable_seen = False
        # Per-minute hints seen this round; the round's wait is their maximum
        # when NOTHING else transient happened (a 5xx or an empty body keeps
        # the ladder — those carry no timing information).
        minute_hints: list[float] = []
        unhinted_retryable = False

        primary = entries[0].provider
        primary_keys = [e for e in entries if e.provider == primary]
        fallbacks = [e for e in entries if e.provider != primary]
        start = _current_key_idx % len(primary_keys)
        ordered = primary_keys[start:] + primary_keys[:start] + fallbacks

        for pos, entry in enumerate(ordered):
            if entry.provider in skipped or _is_unhealthy(entry.provider):
                continue
            # A sibling key's daily-class 429 earlier in THIS round cannot have
            # parked this key, but a provider-level park (Mistral 1300) can.
            if _is_rate_limited(entry.provider, entry.key_idx):
                continue

            model = _model_for(entry.spec, entry.client)
            if not model:
                # Nothing usable behind this provider right now (OpenRouter with
                # no adoptable free model, or its daily quota spent): no API call.
                skipped.add(entry.provider)
                continue
            kwargs: dict = {
                "model": model,
                "messages": messages,
                "temperature": cfg["temperature"],
                "max_tokens": cfg["max_tokens"],
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            kwargs.update(_reasoning_kwargs(entry.provider, model, cfg))

            try:
                response = entry.client.chat.completions.create(**kwargs)
                content = (response.choices[0].message.content or "").strip()

                # An empty body is a FAILURE, not a success. One free OpenRouter
                # model returns HTTP 200 with nothing in it; treating that as valid
                # is exactly how a silent outage starts. For OpenRouter the MODEL
                # is the problem, not the key: demote it so the next entry picks a
                # different candidate instead of retrying the same dead id.
                if not content:
                    logger.warning(
                        "llm_empty_response", provider=entry.provider, model=model
                    )
                    if entry.provider == "openrouter":
                        _drop_openrouter_model(model, "empty response")
                    retryable_seen = True
                    continue

                logger.info(
                    f"{log_name}_success",
                    chars=len(content),
                    provider=entry.provider,
                    model=model,
                    est_tokens=est_tokens,
                )
                # Record who answered so callers can attribute output to a
                # provider (see last_call_provider()).
                _last_call.provider = entry.provider
                _last_call.model = model
                # Advance the rotation only when a PRIMARY key answered, so the
                # next call starts on the primary's next key — never on a fallback.
                if entry.provider == primary:
                    _current_key_idx = (start + pos + 1) % len(primary_keys)
                return content

            except Exception as exc:
                action = _classify(exc)
                last_error = str(exc).replace("\n", " ")[:160]
                limit = _limit_class(exc)
                hint = _retry_hint_seconds(exc) if limit else None
                # `limit=` / `retry_in=` are the fields the raw text cannot show:
                # it is cut before the allowance name (and would carry the org id).
                logger.warning(
                    f"{log_name}_failed",
                    provider=entry.provider,
                    key=entry.key_idx,
                    model=model,
                    action=action,
                    round=round_idx,
                    limit=limit or None,
                    retry_in=round(hint, 1) if hint is not None else None,
                    error=last_error[:110],
                )

                if action == _SKIP_PROVIDER:
                    # A retired/paid-only OpenRouter model is a MODEL problem:
                    # demote it and let the next entry re-resolve, rather than
                    # skipping the whole provider while the cache keeps the dead
                    # id for the rest of the day (the 2026-09-20 shape).
                    if entry.provider == "openrouter" and _classify_is_404(exc):
                        _drop_openrouter_model(model, last_error)
                        retryable_seen = True
                    else:
                        skipped.add(entry.provider)
                elif action == _DISABLE_PROVIDER:
                    _mark_unhealthy(entry.provider, last_error)
                    skipped.add(entry.provider)
                elif limit in _DAILY_LIMIT_CLASSES:
                    # This KEY's bucket is spent for as long as the provider
                    # says. Park it and move to the next key at once — the
                    # sibling keys are separate buckets (L15). Not retryable
                    # within this call: a parked key is filtered next round.
                    _mark_rate_limited(
                        entry.provider,
                        ttl_seconds=_park_seconds_for(exc, entry.provider),
                        reason=last_error,
                        key_idx=entry.key_idx,
                        limit=limit,
                    )
                elif limit == _LIMIT_MISTRAL_1300:
                    # One account, one allowance: park the provider, not the key.
                    _mark_rate_limited(
                        entry.provider,
                        ttl_seconds=MISTRAL_1300_PARK_SECONDS,
                        reason=last_error,
                        limit=limit,
                    )
                    skipped.add(entry.provider)
                else:
                    retryable_seen = True
                    if limit in _PER_MINUTE_LIMIT_CLASSES and hint is not None:
                        minute_hints.append(hint)
                    else:
                        unhinted_retryable = True

        # Nothing transient left to wait for — backing off would only waste time.
        if not retryable_seen or round_idx == len(RETRY_WAIT_TIMES):
            break

        # The next round's wait: the provider's own per-minute hint when that is
        # all this round saw (a burst clears in seconds, not in a 15/30/60/120 s
        # ladder), otherwise the ladder step as before.
        wait = float(RETRY_WAIT_TIMES[round_idx])
        if minute_hints and not unhinted_retryable:
            wait = min(max(minute_hints), HINT_WAIT_MAX_SECONDS)

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


def _throttle() -> None:
    """
    The 15 s soft throttle between calls — skipped when no key can be called at
    all, so a caller that keeps asking an exhausted pool gets its "" in
    milliseconds rather than paying 15 s per item for nothing.
    """
    if pool_exhausted():
        return
    time.sleep(INTER_CALL_SLEEP)


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
    _throttle()
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
    _throttle()
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


# The pre-flight probe's token budget. It was 3, which is what broke the
# generate_static_content cron from 2026-09-08: the pool's primary model is
# `openai/gpt-oss-120b`, a REASONING model that emits internal reasoning tokens
# before any visible content. Three tokens are consumed before `message.content`
# receives a character, so every probe came back empty and every provider was
# declared dead — while research_agent used the same provider and the same model
# successfully all week, because it never caps a call at 3 tokens.
#
# 64 leaves room for a reasoning preamble plus a short reply. The probe stays
# cheap: it is one call, and only on the first healthy key.
_HEALTH_MAX_TOKENS = 64


def check_any_llm_available() -> bool:
    """
    Fast pre-flight / mid-run circuit breaker.

    Answers ONE question: can any key reach a provider right now? It deliberately
    does NOT judge output quality — the generation path already rejects and
    retries empty bodies per call (`llm_empty_response`).

    Tries every KEY until one answers, returning True on the first success. The
    healthy path is therefore still a single call; the full sweep only happens
    when things are actually failing, which is exactly when thoroughness is
    wanted.

    ⚠️ This used to try one key per provider, on the reasoning that "a dead
    provider is dead on every key". That premise is false for a revoked or
    mis-set key AND for quota: Groq meters the free tier per ORGANISATION per
    model on a rolling 24 h window, and the five Groq keys are five accounts —
    five separate buckets — so key #1 being spent says nothing about the other
    four. (#30 had read one truncated 429 as "five keys share one quota"; the
    console read of 2026-09-21 corrected it.) Every key is therefore tried, and a
    key already parked by a daily-class 429 is skipped without a call. (The
    original concern behind the short-circuit was the Cerebras 402 tax; Cerebras
    is no longer in the pool, and these probes are tiny.) Do not reinstate the
    per-provider short-circuit.

    No sleep, no retry ladder — fast enough that the caller can decide whether to
    continue or abort without burning quota.

    Called by: ingestor_service.py, the generate_book_content command, and the
    generate_static_content cron.
    """
    tried: set[str] = set()

    for entry in _pool:
        # Every KEY is tried, not one per provider — each Groq key is its own
        # daily bucket, so one spent key must never declare the provider dead
        # while four full ones sit unused. A key the generation path has already
        # parked for the day is skipped: the answer is known, the call is waste.
        if _is_unhealthy(entry.provider) or _is_rate_limited(
            entry.provider, entry.key_idx
        ):
            continue
        tried.add(entry.provider)

        # The client is passed so a cache-miss OpenRouter resolution is smoke-tested
        # here too, never adopted blind (L11b). "" = nothing usable behind this
        # provider right now — not a failure of the key, just no call to make.
        model = _model_for(entry.spec, entry.client)
        if not model:
            continue
        try:
            response = entry.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Reply: OK"}],
                max_tokens=_HEALTH_MAX_TOKENS,
                temperature=0,
            )
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
            continue

        # The call SUCCEEDED — reachable, authenticated, inside quota. That is
        # the entire question a pre-flight needs to answer, so it returns True
        # even on an empty body.
        #
        # It used to return False there, and that single line took the
        # generate_static_content cron down from 2026-09-08 onwards. An empty
        # body is NOT evidence of an outage: a rate-limited provider raises 429
        # (as Mistral does in those logs), while Groq answered HTTP 200 with
        # nothing in it. Output quality is checked per call in the generation
        # path, which already retries on `llm_empty_response` — availability and
        # quality are different questions and only one of them belongs here.
        if (response.choices[0].message.content or "").strip():
            logger.info("llm_health_ok", provider=entry.provider)
        else:
            logger.warning(
                "llm_health_ok_empty_body",
                provider=entry.provider,
                model=model,
                note="provider reachable; empty body treated as available",
            )
        return True

    logger.error("llm_health_all_failed", pool_size=_pool_size, providers=sorted(tried))
    return False
