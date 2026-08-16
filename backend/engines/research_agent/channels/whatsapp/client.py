"""
engines/research_agent/channels/whatsapp/client.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The single outbound phone line for the WhatsApp channel.

ALL outbound messages MUST route through here — the same discipline
llmops/groq_client.py enforces for LLM calls, and for the same reasons: one
place for retry/backoff, one place for logging, one place to change when the
provider changes.

Provider: Twilio. Plain `requests` — the `twilio` SDK is deliberately NOT a
dependency (CLAUDE.md). Two endpoints do not justify a package.

TRANSPORT NOTES
  - Twilio speaks application/x-www-form-urlencoded, NOT JSON.
  - Auth is HTTP Basic: (ACCOUNT_SID, AUTH_TOKEN).
  - Media is sent as a PUBLIC URL (`MediaUrl`), never an upload — so the
    existing export endpoint is the media source (FEATURE_WHATSAPP.md §3.5).

RETRY POLICY
  Only TRANSIENT failures are retried (timeouts, 5xx, 429). A 4xx means the
  request itself is wrong — retrying cannot fix it, and every attempt burns
  one of the ~100 trial messages. Those raise immediately.

PII
  Phone numbers are masked in every log line (CLAUDE.md). The raw number lives
  only in ra_wa_contact and in the request body itself.
"""

from __future__ import annotations

import time

import requests
import structlog
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from engines.research_agent.channels.whatsapp import config

logger = structlog.get_logger(__name__)


class WhatsAppError(Exception):
    """Send failed and must not be retried (bad request, auth, not configured)."""

    pass


class WhatsAppTransientError(WhatsAppError):
    """Send failed for a reason that may succeed on retry (timeout, 5xx, 429)."""

    pass


class WhatsAppClient:
    """
    Module-level singleton. Stateless per call except for the send-gap clock,
    which exists to preserve message ORDER.
    """

    def __init__(self) -> None:
        self._last_send_at: float = 0.0

    # ──────────────────────────────────────────────────────────────────────────
    # PUBLIC
    # ──────────────────────────────────────────────────────────────────────────
    def send_text(self, to_e164: str, body: str) -> str | None:
        """
        Send a plain text message.

        Returns Twilio's MessageSid, or None when the channel is disabled.
        Raises WhatsAppError on a permanent failure.
        """
        return self._send(
            to_e164,
            {"Body": self._truncate(body)},
            kind="text",
        )

    def send_media(
        self, to_e164: str, media_url: str, caption: str | None = None
    ) -> str | None:
        """
        Send a document/media message by PUBLIC URL.

        Twilio fetches `media_url` itself, so it must be reachable from the
        public internet — the ngrok domain locally, the Render URL in prod.
        A localhost URL here fails silently on Twilio's side.
        """
        payload = {"MediaUrl": media_url}
        if caption:
            payload["Body"] = self._truncate(caption)
        return self._send(to_e164, payload, kind="media")

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────────────────────────────────
    def _send(self, to_e164: str, extra: dict, kind: str) -> str | None:
        """Common path: guard → build → retry → log."""
        if not config.is_operational():
            # Not an error. The flag is off or a key is missing; the channel
            # simply does nothing. Never raise — a disabled channel must not
            # break the worker or the web app.
            logger.info(
                "whatsapp.client.skipped_not_operational",
                kind=kind,
                missing=config.missing_config(),
            )
            return None

        if not self._claim_budget(kind):
            # Ceiling reached. Refuse quietly — same contract as the disabled
            # path above: log, return None, never raise.
            return None

        payload = {
            "From": config.WHATSAPP_FROM,
            "To": config.to_channel(to_e164),
            **extra,
        }

        self._respect_send_gap()

        t0 = time.perf_counter()
        sid = self._post_with_retry(payload)
        duration_ms = int((time.perf_counter() - t0) * 1000)

        logger.info(
            "whatsapp.client.sent",
            kind=kind,
            to=self._mask(to_e164),
            message_sid=sid,
            duration_ms=duration_ms,
        )
        return sid

    def _post_with_retry(self, payload: dict) -> str:
        """
        Retry ONLY transient failures, with exponential backoff.

        `retry_if_exception_type(WhatsAppTransientError)` is the important part:
        a 4xx raises plain WhatsAppError and escapes immediately instead of
        burning three trial messages on a request that can never succeed.
        """
        retryer = Retrying(
            stop=stop_after_attempt(config.MAX_RETRIES),
            wait=wait_exponential(
                multiplier=config.RETRY_BACKOFF_SECONDS, min=1, max=8
            ),
            retry=retry_if_exception_type(WhatsAppTransientError),
            reraise=True,
        )
        return retryer(self._post, payload)

    def _post(self, payload: dict) -> str:
        """One actual HTTP call to Twilio. Returns the MessageSid."""
        try:
            response = requests.post(
                config.messages_url(),
                data=payload,  # form-encoded, NOT json=
                auth=(config.ACCOUNT_SID, config.AUTH_TOKEN),
                timeout=config.HTTP_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            # Connection reset, DNS, timeout — all worth another attempt.
            raise WhatsAppTransientError(f"network error: {exc}") from exc

        if response.status_code in (429, 500, 502, 503, 504):
            raise WhatsAppTransientError(
                f"twilio {response.status_code}: {response.text[:200]}"
            )

        if response.status_code >= 400:
            # 400/401/403 — malformed request, bad credentials, unjoined
            # sandbox recipient. Retrying cannot help.
            raise WhatsAppError(f"twilio {response.status_code}: {response.text[:300]}")

        try:
            return response.json().get("sid", "")
        except ValueError as exc:
            raise WhatsAppError(f"unparseable twilio response: {exc}") from exc

    # ── Outbound budget (Twilio messages only — NOT LLM quota) ───────────────
    def _claim_budget(self, kind: str) -> bool:
        """
        Reserve one message against the lifetime ceiling.

        Counts BEFORE sending, so a send that later fails still consumes its
        slot — Twilio charges for accepted requests, and pretending otherwise
        would let a retry storm slip past the ceiling.

        Redis-backed for the same reason the rate limiter is: an in-memory
        counter would reset on deploy and be wrong across Render workers.
        The key has NO expiry — the trial allowance is a lifetime total.

        FAILS OPEN if Redis is down, matching middleware/rate_limiter.py. A
        limiter's backend being unavailable must never block the feature; the
        channel already depends on Redis for progress events, so a Redis
        outage is a bigger problem than an over-count.
        """
        conn = self._redis()
        if conn is None:
            logger.warning("whatsapp.budget.redis_unavailable_fail_open", kind=kind)
            return True

        try:
            used = conn.incr(config.BUDGET_REDIS_KEY)
        except Exception as exc:
            logger.warning("whatsapp.budget.check_failed_fail_open", error=str(exc))
            return True

        remaining = config.MESSAGE_BUDGET - used

        if used > config.MESSAGE_BUDGET:
            logger.error(
                "whatsapp.budget.exhausted",
                kind=kind,
                used=used,
                budget=config.MESSAGE_BUDGET,
            )
            return False

        if remaining <= config.BUDGET_WARN_THRESHOLD:
            logger.warning(
                "whatsapp.budget.low", remaining=remaining, budget=config.MESSAGE_BUDGET
            )

        return True

    @staticmethod
    def _redis():
        """Same connection helper as middleware/rate_limiter.py."""
        try:
            from django_redis import get_redis_connection

            return get_redis_connection("default")
        except Exception:
            return None

    def budget_status(self) -> dict:
        """Read-only snapshot for verification and debugging. Does not consume."""
        conn = self._redis()
        if conn is None:
            return {"used": None, "budget": config.MESSAGE_BUDGET, "redis": False}
        try:
            raw = conn.get(config.BUDGET_REDIS_KEY)
            used = int(raw) if raw else 0
        except Exception:
            return {"used": None, "budget": config.MESSAGE_BUDGET, "redis": False}
        return {
            "used": used,
            "budget": config.MESSAGE_BUDGET,
            "remaining": config.MESSAGE_BUDGET - used,
            "redis": True,
        }

    def _respect_send_gap(self) -> None:
        """
        Space out consecutive sends.

        Twilio does not guarantee ordering for near-simultaneous messages, and
        the summary → document → prompt sequence is unreadable out of order.
        Enforced here rather than at each call site so no caller can forget.
        """
        elapsed = time.monotonic() - self._last_send_at
        remaining = config.SEND_GAP_SECONDS - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_send_at = time.monotonic()

    @staticmethod
    def _truncate(body: str) -> str:
        """Keep the body inside Twilio's cap, with a visible marker if cut."""
        text = body or ""
        if len(text) <= config.TEXT_MAX_CHARS:
            return text
        return text[: config.TEXT_MAX_CHARS - 1].rstrip() + "…"

    @staticmethod
    def _mask(phone: str) -> str:
        """'+911234567890' → '+91…5618'. Never log a full number."""
        digits = config.from_channel(phone or "")
        return f"{digits[:3]}…{digits[-4:]}" if len(digits) >= 7 else "…"


# Module-level singleton:
#   from engines.research_agent.channels.whatsapp.client import whatsapp_client
whatsapp_client = WhatsAppClient()
