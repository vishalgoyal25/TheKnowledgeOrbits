"""
engines/research_agent/channels/core/http.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Outbound send discipline — identical for every platform.

An adapter knows how to build one HTTP request. Everything AROUND that request
is the same everywhere and lives here:

    · retry, with transient failures distinguished from permanent ones
    · send ordering, so a multi-message reply cannot arrive scrambled
    · a lifetime budget ceiling for metered providers
    · logging that never prints a raw identity

So an adapter's send method is: build the request, hand it to `guarded_send`,
extract the provider's message id. Nothing else.

WHY TRANSIENT vs PERMANENT MATTERS
    A 4xx means the request itself is wrong — retrying cannot fix it, and on a
    metered provider each attempt costs a message. Only timeouts, 429 and 5xx
    are worth a second try. Getting this backwards is how a trial allowance
    disappears in one afternoon.

Retry shape mirrors llmops/groq_client.py deliberately: one discipline for
outbound calls across the whole engine.
"""

from __future__ import annotations

import time
from typing import Callable

import requests
import structlog
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from engines.research_agent.channels.core import constants as k

logger = structlog.get_logger(__name__)

# Status codes worth retrying. Anything else in the 4xx range is our fault and
# will fail identically on every attempt.
TRANSIENT_STATUSES = (408, 429, 500, 502, 503, 504)


class ChannelSendError(Exception):
    """Send failed permanently. Do not retry — the request itself is wrong."""


class ChannelTransientError(ChannelSendError):
    """Send failed for a reason that may succeed on retry."""


class ChannelBlockedError(ChannelSendError):
    """The user blocked the bot or is unreachable. Deactivate; never retry."""


# ──────────────────────────────────────────────────────────────────────────────
# RESPONSE CLASSIFICATION
# ──────────────────────────────────────────────────────────────────────────────


def raise_for_status(
    response: requests.Response,
    *,
    transient: tuple[int, ...] = TRANSIENT_STATUSES,
    blocked: tuple[int, ...] = (403,),
) -> None:
    """
    Turn an HTTP status into the right exception type.

    Adapters call this after their request so the retry layer can tell the
    three cases apart. `blocked` is separate from a plain permanent failure
    because it means "stop talking to this contact", not "fix the request".
    """
    code = response.status_code
    if code < 400:
        return

    body = (response.text or "")[:300]

    if code in transient:
        raise ChannelTransientError(f"{code}: {body}")
    if code in blocked:
        raise ChannelBlockedError(f"{code}: {body}")
    raise ChannelSendError(f"{code}: {body}")


# ──────────────────────────────────────────────────────────────────────────────
# THE GATE — budget + ordering
# ──────────────────────────────────────────────────────────────────────────────


class OutboundGate:
    """
    Module-level singleton guarding every outbound message.

    Ordering state is per-channel and in-process (it only needs to sequence
    sends this worker is making). The budget is per-channel and in Redis,
    because it must hold across workers and survive a deploy.
    """

    def __init__(self) -> None:
        self._last_send_at: dict[str, float] = {}

    # ── Ordering ─────────────────────────────────────────────────────────────
    def wait_for_gap(self, channel: str) -> None:
        """
        Space out consecutive sends on one channel.

        No provider guarantees ordering for near-simultaneous messages, and
        summary → document → prompt is unreadable out of order. Enforced here
        rather than at each call site so no adapter can forget it.
        """
        elapsed = time.monotonic() - self._last_send_at.get(channel, 0.0)
        remaining = k.SEND_GAP_SECONDS - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_send_at[channel] = time.monotonic()

    # ── Budget ───────────────────────────────────────────────────────────────
    def claim_budget(self, channel: str, ceiling: int | None) -> bool:
        """
        Reserve one message against a channel's lifetime ceiling.

        `ceiling=None` means unlimited — the normal case, and a no-op.

        Counts BEFORE sending, because metered providers charge for accepted
        requests. Over-counting a rejection is the safe direction; under-
        counting lets a retry storm past the ceiling.

        NO expiry on the key: a trial allowance is a lifetime total, not a
        daily reset.

        FAILS OPEN if Redis is down, matching middleware/rate_limiter.py. A
        guard's backend being unavailable must never take the feature down.
        """
        if ceiling is None:
            return True

        conn = self._redis()
        if conn is None:
            logger.warning(
                "channel.budget.redis_unavailable_fail_open", channel=channel
            )
            return True

        try:
            used = conn.incr(f"{k.BUDGET_KEY_PREFIX}{channel}")
        except Exception as exc:
            logger.warning(
                "channel.budget.check_failed_fail_open", channel=channel, error=str(exc)
            )
            return True

        if used > ceiling:
            logger.error(
                "channel.budget.exhausted", channel=channel, used=used, ceiling=ceiling
            )
            return False

        remaining = ceiling - used
        if remaining <= k.BUDGET_WARN_THRESHOLD:
            logger.warning("channel.budget.low", channel=channel, remaining=remaining)
        return True

    def budget_status(self, channel: str, ceiling: int | None) -> dict:
        """Read-only snapshot for diagnostics. Does not consume."""
        conn = self._redis()
        if conn is None:
            return {"channel": channel, "ceiling": ceiling, "redis": False}
        try:
            raw = conn.get(f"{k.BUDGET_KEY_PREFIX}{channel}")
            used = int(raw) if raw else 0
        except Exception:
            return {"channel": channel, "ceiling": ceiling, "redis": False}
        return {
            "channel": channel,
            "used": used,
            "ceiling": ceiling,
            "remaining": None if ceiling is None else ceiling - used,
            "redis": True,
        }

    @staticmethod
    def _redis():
        """Same connection helper as middleware/rate_limiter.py."""
        try:
            from django_redis import get_redis_connection

            return get_redis_connection("default")
        except Exception:
            return None


gate = OutboundGate()


# ──────────────────────────────────────────────────────────────────────────────
# THE ONE SEND PATH
# ──────────────────────────────────────────────────────────────────────────────


def guarded_send(
    *,
    channel: str,
    kind: str,
    external_id: str,
    perform: Callable[[], str | None],
    budget: int | None = None,
    max_retries: int = k.MAX_RETRIES,
) -> str | None:
    """
    Run one outbound send with the full discipline applied.

    `perform` does the adapter's HTTP call and returns the provider's message
    id. It should call `raise_for_status()` so failures arrive classified.

    Returns the provider message id, None if the budget refused the send, and
    raises ChannelSendError / ChannelBlockedError on a permanent failure so the
    caller can decide (log, deactivate the contact, mark a delivery failed).

    A refused budget is NOT an error: it logs and returns None, the same
    contract as a disabled channel. Nothing about a guard should crash a worker.
    """
    if not gate.claim_budget(channel, budget):
        return None

    gate.wait_for_gap(channel)

    retryer = Retrying(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=k.RETRY_BACKOFF_SECONDS, min=1, max=8),
        # ONLY transient failures retry. A permanent error escapes on the first
        # attempt instead of burning two more messages on a doomed request.
        retry=retry_if_exception_type(ChannelTransientError),
        reraise=True,
    )

    started = time.perf_counter()
    try:
        message_id = retryer(perform)
    except ChannelBlockedError:
        logger.warning(
            "channel.send.blocked",
            channel=channel,
            kind=kind,
            to=k.mask_identity(external_id),
        )
        raise
    except ChannelSendError as exc:
        logger.error(
            "channel.send.failed",
            channel=channel,
            kind=kind,
            to=k.mask_identity(external_id),
            error=str(exc),
        )
        raise

    logger.info(
        "channel.send.ok",
        channel=channel,
        kind=kind,
        to=k.mask_identity(external_id),
        message_id=message_id,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return message_id


def post_json(
    url: str, payload: dict, *, timeout: int | None = None
) -> requests.Response:
    """
    JSON POST with network errors already classified as transient.

    Connection resets, DNS blips and timeouts are all worth another attempt —
    unlike a 400, which will fail identically forever.
    """
    try:
        return requests.post(
            url, json=payload, timeout=timeout or k.HTTP_TIMEOUT_SECONDS
        )
    except requests.RequestException as exc:
        raise ChannelTransientError(f"network error: {exc}") from exc


def post_form(
    url: str, data: dict, *, auth=None, timeout: int | None = None
) -> requests.Response:
    """Form-encoded POST, for providers that do not speak JSON."""
    try:
        return requests.post(
            url, data=data, auth=auth, timeout=timeout or k.HTTP_TIMEOUT_SECONDS
        )
    except requests.RequestException as exc:
        raise ChannelTransientError(f"network error: {exc}") from exc
