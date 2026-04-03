"""
src/llm_client.py
━━━━━━━━━━━━━━━━━
Shared LLM client for the entire lab.
All modules import from here — one place to configure, rate-limit, and retry.
"""

import os
import time
import logging
from langchain_groq import ChatGroq
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/agent.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("upsc_lab")

# ── LLM Key Pool ─────────────────────────────────────────────────────────────
_model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
_raw_keys = os.getenv("GROQ_API_KEY", "")
_keys = [k.strip() for k in _raw_keys.split(",") if k.strip()]

if not _keys:
    log.error("No GROQ_API_KEY found in environment!")
    _keys = ["DUMMY_KEY"]

_pool_standard = [
    ChatGroq(api_key=k, model_name=_model_name, temperature=0.1, max_tokens=2048)
    for k in _keys
]

_pool_writer = [
    ChatGroq(api_key=k, model_name=_model_name, temperature=0.25, max_tokens=16384)
    for k in _keys
]

_pool_critique = [
    ChatGroq(api_key=k, model_name=_model_name, temperature=0.1, max_tokens=2048)
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
        client = pool[_current_key_idx]

        try:
            response = client.invoke(prompt)
            content = response.content.strip()
            log.info(
                f"  ✅ LLM OK ({len(content)} chars, mode={mode}, KeyIdx={_current_key_idx})"
            )

            # Rotate key on success to balance quota load
            _current_key_idx = (_current_key_idx + 1) % len(_keys)

            return content
        except Exception as e:
            err = str(e).replace("\n", " ")
            log.warning(
                f"  ⚠️  Call failed (KeyIdx={_current_key_idx}, attempt {attempt+1}): {err[:80]}"
            )

            # Rotate key on failure
            last_idx = _current_key_idx
            _current_key_idx = (_current_key_idx + 1) % len(_keys)

            # If we looped fully back around, every key is rate-limited: initiate cooldown.
            if _current_key_idx <= last_idx:  # Looped around to 0
                wait_time_idx = attempt // len(_keys)
                if wait_time_idx < len(RETRY_WAIT_TIMES):
                    wait = RETRY_WAIT_TIMES[wait_time_idx]
                    log.warning(
                        f"  ⏳ All {len(_keys)} keys maxed out. Cooldown: {wait}s..."
                    )
                    time.sleep(wait)

    log.error(
        f"  ❌ LLM permanently failed after {max_retries} attempts across {len(_keys)} keys."
    )
    return ""


def log_info(msg: str):
    log.info(msg)


def log_warning(msg: str):
    log.warning(msg)


def log_error(msg: str):
    log.error(msg)
