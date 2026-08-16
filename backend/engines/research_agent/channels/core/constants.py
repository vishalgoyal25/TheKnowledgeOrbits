"""
engines/research_agent/channels/core/constants.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Vocabulary and policy for the channel layer — identical on every platform.

Everything here was originally written inside `channels/whatsapp/` before the
core + adapter split existed. It lives here now because none of it is
Twilio-, Meta- or Telegram-specific: an enum of message directions and a
30-minute abandon timeout mean the same thing regardless of who delivers the
bytes.

NOTHING platform-specific belongs in this file. Credentials, endpoints, payload
shapes and auth schemes are an adapter's `config.py`. Per-platform *limits*
(text length, button support, media mode) are declared as `Capabilities` by the
adapter — see `adapter.py`.
"""

from __future__ import annotations

import hashlib
import hmac
import os

from django.conf import settings

from engines.research_agent.constants import SessionChannel

# ──────────────────────────────────────────────────────────────────────────────
# MESSAGE VOCABULARY
# ──────────────────────────────────────────────────────────────────────────────


class Direction:
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    ALL = (INBOUND, OUTBOUND)


class MessageType:
    TEXT = "text"
    CALLBACK = "callback"  # a tapped button; carries an action id, not prose
    DOCUMENT = "document"
    PROMPT = "prompt"  # text + an optional action, rendered per capability
    UNSUPPORTED = "unsupported"  # audio/image/location/etc — logged, then declined
    ALL = (TEXT, CALLBACK, DOCUMENT, PROMPT, UNSUPPORTED)


class MessageStatus:
    RECEIVED = "received"
    SENT = "sent"
    FAILED = "failed"
    ALL = (RECEIVED, SENT, FAILED)


# ──────────────────────────────────────────────────────────────────────────────
# CONVERSATION STATE
# ──────────────────────────────────────────────────────────────────────────────


class PendingAction:
    """
    What the contact is expected to send next. NULL means idle.

    Canonical state table: FEATURE_WHATSAPP.md §7.3 — six rows, one exit.
    """

    AWAITING_EMAIL = "awaiting_email"
    ALL = (AWAITING_EMAIL,)


# Action id carried by a prompt. On a platform with buttons this is the callback
# payload; on one without, the user types the keyword instead. Core sends the
# same action either way — the adapter decides how it is rendered.
ACTION_EMAIL_REPORT = "email_report"

# The typed equivalent, for platforms where `supports_buttons` is False.
# Compared case-insensitively.
EMAIL_KEYWORD = "EMAIL"

# How long a pending action stays live before it is treated as abandoned and
# cleared back to NULL. No messaging platform emits a "user dismissed this"
# event, so a TTL is the only way a walked-away user gets unstuck.
PENDING_ACTION_TTL_MINUTES = 30

# Invalid email attempts allowed before giving up and clearing to NULL.
MAX_EMAIL_RETRIES = 1


# ──────────────────────────────────────────────────────────────────────────────
# DELIVERY
# ──────────────────────────────────────────────────────────────────────────────


class DeliveryStatus:
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    ALL = (PENDING, SENT, FAILED)


class DeliveryChannel:
    """
    Where a finished report was handed over.

    Derived from SessionChannel so a new platform is declared in ONE place.
    `web` is excluded deliberately: a browser downloads via ExportView and no
    delivery row is written. `email` is delivery-only — it is never the origin
    of a query.
    """

    EMAIL = "email"
    ALL = tuple(c for c in SessionChannel.ALL if c != SessionChannel.WEB) + (EMAIL,)


# ──────────────────────────────────────────────────────────────────────────────
# OUTBOUND HTTP POLICY (mechanism lives in http.py)
# ──────────────────────────────────────────────────────────────────────────────

# Outbound sends run in the background worker, never the request thread, so a
# blocking timeout is safe.
HTTP_TIMEOUT_SECONDS = 15

# Retry/backoff mirrors llmops/groq_client.py — same discipline, same shape.
# Only TRANSIENT failures are retried; a 4xx means the request itself is wrong
# and retrying cannot fix it (and on metered providers, costs a message).
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 1.5

# Gap between consecutive outbound messages. No platform guarantees ordering for
# near-simultaneous sends, and summary → document → prompt is unreadable out of
# order. Enforced centrally so no caller can forget.
SEND_GAP_SECONDS = 0.4

# Redis key prefix for the per-channel outbound budget. The ceiling itself is
# declared by each adapter (None = unlimited) — a metered trial account needs a
# hard stop, an unmetered platform does not.
BUDGET_KEY_PREFIX = "channel:outbound:"
BUDGET_WARN_THRESHOLD = 15


# ──────────────────────────────────────────────────────────────────────────────
# PII
# ──────────────────────────────────────────────────────────────────────────────
# Raw identities (phone, chat_id, username, email) live ONLY in
# ra_channel_contact. Everything downstream — ResearchSession.channel_ref,
# Langfuse, Sentry, logs — sees a hash or a mask. One rule, enforced once.

# Keyed hashing, not plain SHA-256. The space of phone numbers and chat ids is
# small enough to brute-force a bare digest, and these hashes reach Langfuse,
# a third-party service. A dedicated salt keeps PII hashing independent of
# Django's SECRET_KEY, which may be rotated for unrelated reasons.
#
# ⚠️ Rotating this value re-hashes every identity: existing contacts stop
# matching their sessions and per-contact rate limits reset. Set it once.
_HASH_SALT = os.getenv("CHANNEL_HASH_SALT", "") or getattr(settings, "SECRET_KEY", "")


def hash_identity(raw: str) -> str:
    """
    Stable, keyed hash of an external identity. 64 hex chars — matches
    ResearchSession.channel_ref and ChannelContact.external_hash.

    This is what may travel to Langfuse and Sentry. The raw value may not.
    """
    return hmac.new(
        _HASH_SALT.encode("utf-8"),
        (raw or "").strip().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def mask_identity(raw: str) -> str:
    """
    Human-readable but non-identifying form, for log lines.

        '+911234567890'  → '+91…7890'
        '987654321'      → '987…4321'

    Short or empty values collapse to '…' rather than leaking themselves.
    """
    value = (raw or "").strip()
    return f"{value[:3]}…{value[-4:]}" if len(value) >= 9 else "…"
