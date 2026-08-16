"""
engines/research_agent/channels/whatsapp/config.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WhatsApp channel configuration — read from the environment ONLY.

Provider: Twilio WhatsApp Sandbox (see FEATURE_WHATSAPP.md §3.3 — chosen over
Meta Cloud API because it needs no Facebook developer account).

`core/settings/` is frozen (CLAUDE.md → DO NOT TOUCH), so no Django settings
entries are added for this feature. Values come from `backend/.env`, which
`core/settings/base.py` already loads into `os.environ` via
`environ.Env.read_env()` — so plain `os.getenv` sees everything.

Nothing here raises on import. A missing key must never break `migrate`,
`collectstatic` or the web app; it only disables the channel. Use
`missing_config()` to find out what is absent.
"""

from __future__ import annotations

import os

# Shared policy lives in core — an adapter may import core, never the reverse.
# The names below are re-exported so this held module keeps working unchanged
# while having exactly ONE definition of each value.
from engines.research_agent.channels.core import constants as core_k

# ──────────────────────────────────────────────────────────────────────────────
# CREDENTIALS (see FEATURE_WHATSAPP.md §9)
# ──────────────────────────────────────────────────────────────────────────────

# Master kill switch. Deployed OFF; flipped on only after the prod smoke test
# (Phase 8). Turning it off is the rollback path — nothing else is affected.
ENABLED: bool = os.getenv("WHATSAPP_ENABLED", "False").strip().lower() in (
    "true",
    "1",
    "yes",
)

# Twilio Console → dashboard. The SID is also part of every API URL.
ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "").strip()

# Twilio Console → dashboard. Serves DOUBLE duty:
#   1. HTTP Basic auth password for outbound API calls
#   2. the HMAC-SHA1 key Twilio signs inbound webhooks with
# So a wrong token breaks BOTH sending and inbound authentication.
AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "").strip()

# Sender, WITH Twilio's channel prefix — e.g. "whatsapp:+1XXXXXXXXXX".
# Twilio's newer Tryout UI uses your trial number rather than the classic
# shared sandbox number — never hardcode either; both come from the env.
WHATSAPP_FROM: str = os.getenv("TWILIO_WHATSAPP_FROM", "").strip()

# Public base URL of THIS backend — the ngrok static domain locally, the Render
# URL in production. No trailing slash.
#
# Used for TWO things, and a stale value breaks both:
#   1. media URLs handed to Twilio (§3.5)
#   2. signature validation, which recomputes the HMAC over the exact URL
#      Twilio called — a mismatch reads as a forged request
BACKEND_PUBLIC_URL: str = os.getenv("BACKEND_PUBLIC_URL", "").strip().rstrip("/")


# ──────────────────────────────────────────────────────────────────────────────
# ROUTES
# ──────────────────────────────────────────────────────────────────────────────

# Path this channel's webhook is mounted at. Kept here (not just in urls.py)
# because signature validation must rebuild the exact absolute URL Twilio hit.
WEBHOOK_PATH: str = "/api/v1/research/whatsapp/webhook/"


def messages_url() -> str:
    """Twilio endpoint every outbound message is POSTed to."""
    return f"https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT_SID}/Messages.json"


def webhook_url() -> str:
    """
    The absolute URL Twilio calls. MUST match what Twilio has configured,
    character for character — signature validation depends on it.
    """
    return f"{BACKEND_PUBLIC_URL}{WEBHOOK_PATH}"


def export_url(session_id: str, fmt: str = "pdf") -> str:
    """
    Public URL of an existing report export.

    This is the ONE media path (CLAUDE.md) — the same URL feeds the WhatsApp
    media message and the emailed attachment. We never build a second PDF
    route and never re-render.
    """
    return f"{BACKEND_PUBLIC_URL}/api/v1/research/export/{session_id}/?format={fmt}"


# ──────────────────────────────────────────────────────────────────────────────
# PLATFORM LIMITS (Twilio / WhatsApp facts — not configurable)
# ──────────────────────────────────────────────────────────────────────────────

# Twilio caps a WhatsApp message body at 1600 chars. `executive_summary` is
# ~300 words (~2000 chars), so the summary IS truncated — the full text always
# travels in the attached document instead.
TEXT_MAX_CHARS: int = 1600

# Twilio's channel prefix on both `From` and `To`.
CHANNEL_PREFIX: str = "whatsapp:"

# The sandbox has no interactive buttons, so the email flow is triggered by a
# typed keyword (FEATURE_WHATSAPP.md §3.4). The keyword itself is core policy —
# platforms differ only in whether a button is offered instead.
EMAIL_KEYWORD: str = core_k.EMAIL_KEYWORD


# ──────────────────────────────────────────────────────────────────────────────
# HTTP BEHAVIOUR (used by client.py)
# ──────────────────────────────────────────────────────────────────────────────

# Defined once in core/constants.py — timeouts, retry discipline and send
# ordering are identical on every platform, so they are re-exported here rather
# than restated.
HTTP_TIMEOUT_SECONDS: int = core_k.HTTP_TIMEOUT_SECONDS
MAX_RETRIES: int = core_k.MAX_RETRIES
RETRY_BACKOFF_SECONDS: float = core_k.RETRY_BACKOFF_SECONDS
SEND_GAP_SECONDS: float = core_k.SEND_GAP_SECONDS


# ──────────────────────────────────────────────────────────────────────────────
# OUTBOUND MESSAGE BUDGET
# ──────────────────────────────────────────────────────────────────────────────
# A hard ceiling on TWILIO messages this channel will ever send. Nothing to do
# with LLM quotas — those live in middleware/rate_limiter.py (per-provider RPM)
# and constants.py (PUBLIC_DAILY_LIMIT), and are untouched by this feature.
#
# Why it exists: the Twilio trial grants a finite number of free messages. A
# runaway loop would drain them silently, and past the free tier it spends real
# credit. At the ceiling the client refuses to send and logs — it does NOT
# raise, so nothing fails at runtime.
#
# Raise this (or set it very high) once the account is off the trial.
MESSAGE_BUDGET: int = int(os.getenv("WHATSAPP_MESSAGE_BUDGET", "90"))

# Cumulative counter — deliberately NO expiry. The trial allowance is a total,
# not a daily reset, so this must not roll over at midnight. The key prefix and
# the warning threshold are core policy; only the ceiling above is per-adapter
# (and becomes a `Capabilities.outbound_budget` value when this is rebuilt).
BUDGET_REDIS_KEY: str = f"{core_k.BUDGET_KEY_PREFIX}whatsapp"
BUDGET_WARN_THRESHOLD: int = core_k.BUDGET_WARN_THRESHOLD


# ──────────────────────────────────────────────────────────────────────────────
# CONVERSATION STATE (used by state.py — Phase 6)
# ──────────────────────────────────────────────────────────────────────────────

# State-machine policy is core (FEATURE_WHATSAPP.md §7.3) — the TTL and retry
# budget mean the same thing on every platform. Re-exported, not restated.
PENDING_ACTION_TTL_MINUTES: int = core_k.PENDING_ACTION_TTL_MINUTES
MAX_EMAIL_RETRIES: int = core_k.MAX_EMAIL_RETRIES


# ──────────────────────────────────────────────────────────────────────────────
# PHONE HELPERS
# ──────────────────────────────────────────────────────────────────────────────
# Twilio speaks "whatsapp:+911234567890"; we store bare E.164 ("+911234567890")
# in ra_wa_contact. The prefix is added/stripped at the client boundary only.


def to_channel(phone_e164: str) -> str:
    """'+911234567890' → 'whatsapp:+911234567890' (idempotent)."""
    phone = (phone_e164 or "").strip()
    return phone if phone.startswith(CHANNEL_PREFIX) else f"{CHANNEL_PREFIX}{phone}"


def from_channel(channel_address: str) -> str:
    """'whatsapp:+911234567890' → '+911234567890' (idempotent)."""
    addr = (channel_address or "").strip()
    return addr[len(CHANNEL_PREFIX) :] if addr.startswith(CHANNEL_PREFIX) else addr


# ──────────────────────────────────────────────────────────────────────────────
# HEALTH
# ──────────────────────────────────────────────────────────────────────────────

# Keys without which the channel cannot function at all.
_REQUIRED = (
    ("TWILIO_ACCOUNT_SID", ACCOUNT_SID),
    ("TWILIO_AUTH_TOKEN", AUTH_TOKEN),
    ("TWILIO_WHATSAPP_FROM", WHATSAPP_FROM),
    ("BACKEND_PUBLIC_URL", BACKEND_PUBLIC_URL),
)


def missing_config() -> list[str]:
    """Names of required env vars that are absent or blank."""
    return [name for name, value in _REQUIRED if not value]


def is_operational() -> bool:
    """True only when the flag is on AND every required key is present."""
    return ENABLED and not missing_config()
