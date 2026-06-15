"""
engines/research_agent/middleware/rate_limiter.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Redis-backed rate limiter. MUST be Redis-backed — an in-memory limiter breaks
across multiple Render workers (Risk #2). Two independent limiters live here:

1. PER-USER DAILY QUERY LIMIT (Risk: abuse / cost)
   - Anonymous users: PUBLIC_DAILY_LIMIT queries/day, keyed by real client IP.
   - Authenticated users: unlimited.
   - Enforced in query_view BEFORE a session/task is created.

2. GLOBAL PER-PROVIDER RPM LIMIT (Risk #6 / #7)
   - Groq 30 RPM, Cerebras 60 RPM — shared across ALL workers.
   - Enforced inside groq_client BEFORE each LLM call. When a provider is at its
     cap, the limiter raises → the pool's failover loop SKIPS it and tries the
     other provider. This pre-emptively spreads load and avoids upstream 429s.

GRACEFUL FALLBACK: if Redis is unavailable, both limiters FAIL OPEN (allow the
request) — never block real users because the limiter's backend is down.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import structlog

from engines.research_agent.constants import (
    PUBLIC_DAILY_LIMIT,
    GROQ_REQUESTS_PER_MINUTE,
    CEREBRAS_REQUESTS_PER_MINUTE,
)

logger = structlog.get_logger(__name__)

# Daily query caps (per rolling 24h, keyed by identity).
#   anonymous     → PUBLIC_DAILY_LIMIT (from constants)
#   authenticated → AUTH_DAILY_LIMIT
AUTH_DAILY_LIMIT = 10

_DAILY_KEY = "research:ratelimit:daily:{identity}:{day}"
_RPM_KEY = "research:ratelimit:rpm:{provider}:{minute}"
_DAY_TTL = 24 * 3600
_MINUTE_TTL = 70  # slightly over a minute so the window can't be evicted early

_PROVIDER_RPM = {
    "groq": GROQ_REQUESTS_PER_MINUTE,
    "cerebras": CEREBRAS_REQUESTS_PER_MINUTE,
}


class RateLimitExceeded(Exception):
    """Raised by the per-provider limiter so the LLM pool fails over."""

    pass


class RedisRateLimiter:
    """Module-level singleton. All state lives in Redis (shared across workers)."""

    # ──────────────────────────────────────────────────────────────────────────
    # 1. Per-user daily query limit (query_view)
    # ──────────────────────────────────────────────────────────────────────────
    def check_query_limit(
        self,
        ip: str | None,
        is_authenticated: bool,
        user_id: str | None = None,
    ) -> tuple[bool, int]:
        """
        Returns (allowed, remaining). Counts the current request.

          - Authenticated → AUTH_DAILY_LIMIT/day, keyed by user_id (follows the
            user across IPs/devices).
          - Anonymous     → PUBLIC_DAILY_LIMIT/day, keyed by IP.

        Fails OPEN if Redis is down.
        """
        limit = AUTH_DAILY_LIMIT if is_authenticated else PUBLIC_DAILY_LIMIT

        conn = self._redis()
        if conn is None:
            return True, limit  # fail open

        try:
            identity = (
                f"user:{user_id}" if is_authenticated else f"ip:{ip or 'unknown'}"
            )
            key = _DAILY_KEY.format(identity=identity, day=date.today().isoformat())
            count = conn.incr(key)
            if count == 1:
                conn.expire(key, _DAY_TTL)
            remaining = max(0, limit - count)
            allowed = count <= limit
            if not allowed:
                logger.info(
                    "research_agent.ratelimit.daily_blocked",
                    identity=identity,
                    count=count,
                    limit=limit,
                )
            return allowed, remaining
        except Exception as exc:
            logger.warning("research_agent.ratelimit.daily_error", error=str(exc))
            return True, limit  # fail open

    # ──────────────────────────────────────────────────────────────────────────
    # 2. Global per-provider RPM (groq_client._check_rate_limit)
    # ──────────────────────────────────────────────────────────────────────────
    def check_provider_rpm(self, provider: str) -> None:
        """
        Increments this provider's per-minute counter. Raises RateLimitExceeded
        if it's over the cap (so the LLM pool fails over to the other provider).
        Fails OPEN if Redis is down or the provider has no configured cap.
        """
        limit = _PROVIDER_RPM.get(provider)
        if limit is None:
            return

        conn = self._redis()
        if conn is None:
            return  # fail open

        try:
            minute = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
            key = _RPM_KEY.format(provider=provider, minute=minute)
            count = conn.incr(key)
            if count == 1:
                conn.expire(key, _MINUTE_TTL)
            if count > limit:
                logger.info(
                    "research_agent.ratelimit.rpm_capped",
                    provider=provider,
                    count=count,
                    limit=limit,
                )
                raise RateLimitExceeded(f"{provider} RPM cap {limit} reached")
        except RateLimitExceeded:
            raise
        except Exception as exc:
            logger.warning(
                "research_agent.ratelimit.rpm_error", provider=provider, error=str(exc)
            )
            return  # fail open

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────────────────────────────────
    def _redis(self):
        try:
            from django_redis import get_redis_connection

            return get_redis_connection("default")
        except Exception:
            return None


# Module-level singleton.
rate_limiter = RedisRateLimiter()
