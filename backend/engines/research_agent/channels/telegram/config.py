"""
engines/research_agent/channels/telegram/config.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Telegram credentials, endpoints and declared capabilities.

Read from the environment ONLY. `core/settings/` is frozen (CLAUDE.md), so this
feature adds no Django settings entries — `backend/.env` is already loaded into
`os.environ` by `core/settings/base.py`.

Nothing here raises on import. A missing token must never break `migrate`,
`collectstatic` or the web app; it only makes the channel non-operational, and
the registry logs which key is absent.

⚠️ THE REPO IS PUBLIC. Only env var NAMES appear in this file — never a token,
never a chat id, never a domain.
"""

from __future__ import annotations

import os

from engines.research_agent.channels.core.adapter import Capabilities, MediaMode

# ──────────────────────────────────────────────────────────────────────────────
# CREDENTIALS
# ──────────────────────────────────────────────────────────────────────────────

# Master kill switch for this channel alone. Deployed OFF; flipped on only after
# the prod smoke test (T8). Turning it off is the rollback path — no other
# channel and nothing on the web path is affected.
ENABLED: bool = os.getenv("TELEGRAM_ENABLED", "False").strip().lower() in (
    "true",
    "1",
    "yes",
)

# From @BotFather. Doubles as the API path segment, which is why it must never
# be logged: a leaked token IS full control of the bot.
BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

# A string we invent and hand to setWebhook. Telegram then echoes it back in the
# X-Telegram-Bot-Api-Secret-Token header on every update. That header is this
# webhook's ONLY authentication — the documented exemption to the
# RBAC-decorator rule.
WEBHOOK_SECRET: str = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()


# ──────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ──────────────────────────────────────────────────────────────────────────────


def api_url(method: str) -> str:
    """
    Absolute Bot API URL, e.g. api_url('sendMessage').

    The token sits in the PATH rather than a header — a Telegram quirk. It makes
    accidental logging of a full request URL a credential leak, so request URLs
    are never logged; core/http.py logs only channel, kind and a masked id.
    """
    return f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"


# ──────────────────────────────────────────────────────────────────────────────
# CAPABILITIES — what core reads instead of asking "is this Telegram?"
# ──────────────────────────────────────────────────────────────────────────────

CAPABILITIES = Capabilities(
    # Telegram's own cap on one text message. Nearly 2.6x WhatsApp's 1600, so
    # an executive summary fits without truncation here and does not there —
    # core handles both by reading this number.
    max_text_chars=4096,
    # Inline keyboards are supported, so the email prompt is a real tappable
    # button and taps arrive as callback queries. Core sends the same action
    # either way; only the rendering differs.
    supports_buttons=True,
    # Telegram fetches documents from a public URL — the existing export
    # endpoint feeds it directly, with no upload step.
    media_mode=MediaMode.URL,
    # Telegram's limit when it fetches by URL (uploads may go higher). Reports
    # are orders of magnitude below this.
    max_media_bytes=20 * 1024 * 1024,
    # No metering: the Bot API is free with no message allowance. The budget
    # guard exists for providers like Twilio's trial, which charges per accepted
    # request; here it stays off.
    outbound_budget=None,
)


# ──────────────────────────────────────────────────────────────────────────────
# HEALTH
# ──────────────────────────────────────────────────────────────────────────────

_REQUIRED = (
    ("TELEGRAM_BOT_TOKEN", BOT_TOKEN),
    ("TELEGRAM_WEBHOOK_SECRET", WEBHOOK_SECRET),
)


def missing_config() -> list[str]:
    """Names of required env vars that are absent or blank. Never values."""
    return [name for name, value in _REQUIRED if not value]


def is_operational() -> bool:
    """
    True only when the flag is on AND every credential is present.

    The flag alone is not enough: `TELEGRAM_ENABLED=True` with a blank secret
    would accept unauthenticated webhooks.
    """
    return ENABLED and not missing_config()
