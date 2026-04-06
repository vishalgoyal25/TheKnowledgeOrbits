"""
engines/book_content/services/llm_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Shared LLM client for the Book Content Engine.
All services import llm_call from here — one place to configure, rate-limit, and retry.
Ported from: upsc-agent-lab/src/llm_client.py
Changes: imports, logging (structlog), settings integration, Sentry on permanent failure.
Preserved exactly: pool config, rate limits, retry logic, key rotation algorithm.
"""

import time

from django.conf import settings

import sentry_sdk
import structlog
from langchain_groq import ChatGroq
from pydantic.v1 import SecretStr

logger = structlog.get_logger(__name__)

# ── LLM Key Pool ──────────────────────────────────────────────────────────────
_model_name = getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")
_raw_keys = getattr(settings, "GROQ_API_KEY", "")
_keys = [k.strip() for k in _raw_keys.split(",") if k.strip()]

if not _keys:
    logger.error(
        "groq_api_key_missing", message="No GROQ_API_KEY found in Django settings!"
    )
    _keys = ["DUMMY_KEY"]

_pool_standard = [
    ChatGroq(
        api_key=SecretStr(k),
        model=_model_name,
        temperature=0.1,
        max_tokens=2048,
        stop_sequences=[],
    )
    for k in _keys
]

_pool_writer = [
    ChatGroq(
        api_key=SecretStr(k),
        model=_model_name,
        temperature=0.25,
        max_tokens=16384,
        stop_sequences=[],
    )
    for k in _keys
]

_pool_critique = [
    ChatGroq(
        api_key=SecretStr(k),
        model=_model_name,
        temperature=0.1,
        max_tokens=2048,
        stop_sequences=[],
    )
    for k in _keys
]

_current_key_idx = 0

# ── Rate Limit Config ─────────────────────────────────────────────────────────
INTER_CALL_SLEEP = 12.0  # Soft throttle for 6,000 tokens/min Groq free tier limit
RETRY_WAIT_TIMES = [15, 30, 45]  # Loop delays when entire key pool is exhausted


# ── Core Call Wrapper ─────────────────────────────────────────────────────────
def llm_call(prompt: str, mode: str = "standard") -> str:
    """
    Makes a single LLM call with a Round-Robin Multi-Key Pool to bypass Rate Limits.

    Args:
        prompt: The full prompt string to send to the LLM.
        mode:   Pool selector — 'standard' | 'writer' | 'critique'
                writer   → temperature=0.25, max_tokens=16384  (long article generation)
                critique → temperature=0.1,  max_tokens=2048   (self-critique pass)
                standard → temperature=0.1,  max_tokens=2048   (classification, planning)

    Returns:
        LLM response string. Empty string on permanent failure.
    """
    global _current_key_idx

    # Always sleep to soften rate-limits across the board
    time.sleep(INTER_CALL_SLEEP)

    attempts_per_run = len(RETRY_WAIT_TIMES) * len(_keys)
    max_retries = attempts_per_run

    for attempt in range(max_retries):
        if mode == "writer":
            pool = _pool_writer
        elif mode == "critique":
            pool = _pool_critique
        else:
            pool = _pool_standard
        if not pool:
            break
        key_idx = _current_key_idx % len(pool)
        client = pool[key_idx]

        try:
            response = client.invoke(prompt)
            content = str(response.content).strip()
            logger.info(
                "llm_call_success",
                chars=len(content),
                mode=mode,
                key_idx=_current_key_idx,
            )

            # Rotate key on success to balance quota load
            _current_key_idx = (_current_key_idx + 1) % len(_keys)

            return content

        except Exception as e:
            err = str(e).replace("\n", " ")
            logger.warning(
                "llm_call_failed",
                key_idx=_current_key_idx,
                attempt=attempt + 1,
                error=err[:80],
            )

            # Rotate key on failure
            last_idx = _current_key_idx
            _current_key_idx = (_current_key_idx + 1) % len(_keys)

            # If we looped fully back around, every key is rate-limited: initiate cooldown.
            if _current_key_idx <= last_idx:  # Looped around to 0
                wait_time_idx = attempt // len(_keys)
                if wait_time_idx < len(RETRY_WAIT_TIMES):
                    wait = RETRY_WAIT_TIMES[wait_time_idx]
                    logger.warning(
                        "llm_all_keys_exhausted",
                        num_keys=len(_keys),
                        cooldown_seconds=wait,
                    )
                    time.sleep(wait)

    logger.error(
        "llm_permanently_failed",
        max_retries=max_retries,
        num_keys=len(_keys),
    )
    sentry_sdk.capture_message(
        f"LLM permanently failed after {max_retries} attempts across {len(_keys)} keys.",
        level="error",
    )
    return ""
