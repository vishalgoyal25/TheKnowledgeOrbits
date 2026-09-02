"""
Telemetry Engine — shared internals.

Both writers (the request middleware and the read beacon) derive identity and
read configuration through this module. That is the point of it: if the two
salted IPs differently, or disagreed about whether telemetry is switched on,
the same visitor would land in telemetry_visit_log and telemetry_content_read
under DIFFERENT ip_hash values — and nothing would ever compare correctly
between the two tables again. One implementation, one behaviour.

Configuration is read from the environment directly rather than from Django
settings, matching the existing pattern in engines/daily_ca (image_service.py)
and engines/content (embedding_service.py), and keeping core/settings/ free of
telemetry-specific keys.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

import structlog
from django.core.cache import cache

logger = structlog.get_logger(__name__)

# Beacon rate limit defaults. Generous on purpose: a real reader fires one
# beacon per article per page load, so a human never approaches this. It exists
# to stop a script filling the table and exhausting the Supabase ceiling (R2),
# not to police normal browsing.
DEFAULT_BEACON_RATE_LIMIT = 120
DEFAULT_BEACON_RATE_WINDOW = 3600  # seconds


def env_flag(name: str, default: bool = False) -> bool:
    """Read a boolean env var. Anything unrecognised falls back to `default`."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    """Read an integer env var, falling back on anything unparseable."""
    try:
        return int(os.getenv(name, "").strip())
    except (TypeError, ValueError):
        return default


def ip_salt() -> str:
    """The hashing salt. Empty string means 'not configured'."""
    return os.getenv("TELEMETRY_IP_SALT", "").strip()


def is_enabled() -> bool:
    """
    Master switch for the whole telemetry layer.

    Returns False when TELEMETRY_ENABLED is off, AND — deliberately — when the
    salt is missing. That second case is FAIL SAFE, not fail open: an unsalted
    SHA-256 of an IPv4 address is reversible by enumerating the whole address
    space in seconds, so a forgotten env var must stop collection rather than
    quietly produce data that looks pseudonymous and is not.
    """
    if not env_flag("TELEMETRY_ENABLED", default=False):
        return False
    return bool(ip_salt())


def client_ip(request: Any) -> str:
    """
    Real client IP — X-Forwarded-For aware.

    Render sits behind a load balancer, so REMOTE_ADDR is the PROXY. Using it
    would hash one identical value for every request in production while
    looking perfectly correct on localhost. Mirrors the existing helper in
    engines/research_agent/views/query_view.py.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def hash_ip(request: Any) -> str:
    """Salted SHA-256. The raw IP is never stored, logged or sent onward."""
    digest = hashlib.sha256(f"{ip_salt()}{client_ip(request)}".encode())
    return digest.hexdigest()


def report(exc: Exception) -> None:
    """
    Best-effort Sentry report. NEVER raises.

    Sentry is a free-tier dependency: the trial lapses, the quota fills, a DSN
    gets revoked. None of that may affect serving traffic, so a failure to
    REPORT an error is itself swallowed. Observability is a convenience;
    availability is not.
    """
    try:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
    except Exception:  # noqa: BLE001 — reporting must never break the caller
        logger.debug("sentry_report_failed")


def within_rate_limit(identity: str) -> bool:
    """
    Redis-backed fixed-window limiter for the public beacon.

    Uses django.core.cache, which is Redis in production — the same backend
    RBACMiddleware already relies on. It MUST be shared state: an in-memory
    counter would reset per worker and per restart, so it would not limit
    anything on Render.

    FAILS OPEN. If Redis is unreachable the request is allowed through, exactly
    as engines/research_agent/middleware/rate_limiter.py does. Never block a
    real reader because the limiter's backend is down — the storage ceiling is
    a real risk, but a limiter outage must not become a site outage.
    """
    limit = env_int("TELEMETRY_BEACON_RATE_LIMIT", DEFAULT_BEACON_RATE_LIMIT)
    window = env_int("TELEMETRY_BEACON_RATE_WINDOW", DEFAULT_BEACON_RATE_WINDOW)
    key = f"telemetry:beacon:{identity}"

    try:
        # add() only succeeds when the key is absent, which both starts the
        # window and avoids incr()'s ValueError on a missing key.
        if cache.add(key, 1, timeout=window):
            return True
        return int(cache.incr(key)) <= limit
    except Exception as exc:  # noqa: BLE001
        report(exc)
        logger.warning("telemetry_rate_limit_unavailable", error=str(exc)[:200])
        return True
