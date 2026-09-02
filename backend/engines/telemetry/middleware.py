"""
Telemetry Engine — request logging middleware.

Writes one VisitLog row per server-visible request that survives filtering.

Placement
─────────
Must sit AFTER django.contrib.auth's AuthenticationMiddleware, or
`request.user` does not exist yet and `is_authenticated` would be wrong on
every row. Registered in BOTH core/settings/base.py and core/settings/prod.py
— prod.py redefines MIDDLEWARE wholesale rather than extending base, so
editing only base.py works locally and is silently dead in production.

Style
─────
Plain callable rather than MiddlewareMixin, because the row needs the
response status code.

Non-negotiable: telemetry NEVER breaks a request
────────────────────────────────────────────────
Every failure path here is swallowed, reported to Sentry, and logged. A
request must be served correctly even if the telemetry write fails outright.

Why a direct INSERT and not a queue
───────────────────────────────────
django-background-tasks persists each task AS a database row, so deferring
the write would cost an insert plus a delete — strictly more writes than
writing once. An in-memory buffer would lose rows on restart and grow memory
on a 512 MB dyno already shared with process_tasks. Volume is controlled by
filtering, which is what the skip rules below are for.

Identity and config come from utils.py so that this middleware and the read
beacon derive ip_hash identically — see that module's docstring.
"""

from __future__ import annotations

from typing import Any

import structlog

from engines.telemetry.models import (
    MAX_PATH_LENGTH,
    MAX_REFERRER_LENGTH,
    MAX_USER_AGENT_LENGTH,
    VisitLog,
)
from engines.telemetry.utils import env_flag, hash_ip, is_enabled, report

logger = structlog.get_logger(__name__)

# Paths that never produce a row. Static assets and health checks are noise;
# /admin is the operator, not a visitor; /api/v1/telemetry/ would be telemetry
# about telemetry.
SKIP_PATH_PREFIXES = (
    "/static/",
    "/media/",
    "/admin/",
    "/favicon.ico",
    "/api/v1/health",
    "/api/v1/telemetry/",
)

# Lower-cased User-Agent substrings that mark automated traffic. Deliberately
# short: the authoritative filter is _is_machine_traffic() below, and this list
# only catches self-identifying clients.
BOT_USER_AGENT_MARKERS = (
    "bot",
    "crawler",
    "spider",
    "slurp",
    "curl",
    "wget",
    "python-requests",
    "node-fetch",
    "axios",
    "headless",
    "lighthouse",
    "vercel",
)


class TelemetryMiddleware:
    """Records one VisitLog row per qualifying request."""

    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response

        # Logged once at boot purely as a diagnostic — the live check happens
        # per request in __call__, so flipping TELEMETRY_ENABLED takes effect
        # without a code change here.
        enabled = is_enabled()
        if env_flag("TELEMETRY_ENABLED") and not enabled:
            logger.warning(
                "telemetry_disabled_missing_salt",
                reason="TELEMETRY_IP_SALT is unset; refusing to store weakly hashed IPs",
            )
        logger.info("telemetry_middleware_initialised", enabled=enabled)

    def __call__(self, request: Any) -> Any:
        response = self.get_response(request)

        if not is_enabled():
            return response

        try:
            if self._should_record(request, response):
                self._record(request, response)
        except Exception as exc:  # noqa: BLE001 — telemetry must never 500 a request
            report(exc)
            logger.warning(
                "telemetry_write_failed",
                path=request.path[:MAX_PATH_LENGTH],
                error=str(exc)[:200],
            )

        return response

    # ── Filtering ─────────────────────────────────────────────────────────────

    def _should_record(self, request: Any, response: Any) -> bool:
        """Decide whether this request earns a row."""

        # Streaming responses are Server-Sent Events (research_agent) or file
        # downloads. Recording one would write a row per heartbeat, and touching
        # the response risks disturbing the stream. Checking the response type
        # is exact — no path guessing.
        if getattr(response, "streaming", False):
            return False

        path = request.path
        if path.startswith(SKIP_PATH_PREFIXES):
            return False

        if self._is_machine_traffic(request):
            return False

        return True

    @staticmethod
    def _is_machine_traffic(request: Any) -> bool:
        """
        Distinguish machines from people.

        The primary signal is the absence of `Sec-Fetch-Mode`. Every current
        browser sends the Sec-Fetch-* family on every request; server-side
        fetches do not. That matters here specifically because Vercel's ISR
        regeneration calls this API on every rebuild, and those requests are
        rebuilds — not readers. Left unfiltered they would be the single
        largest source of junk rows and would make every "hot endpoint" figure
        wrong.

        This is a heuristic and is expected to be refined: after a week of real
        data, query the collected user_agent values and extend
        BOT_USER_AGENT_MARKERS with whatever actually shows up. Do not guess it
        in advance.
        """
        if "HTTP_SEC_FETCH_MODE" not in request.META:
            return True

        user_agent = request.META.get("HTTP_USER_AGENT", "").lower()
        return any(marker in user_agent for marker in BOT_USER_AGENT_MARKERS)

    # ── Write ─────────────────────────────────────────────────────────────────

    def _record(self, request: Any, response: Any) -> None:
        """One INSERT. No `.using()` — `default` is Supabase in production."""
        user = getattr(request, "user", None)
        is_authenticated = bool(user is not None and user.is_authenticated)

        VisitLog.objects.create(
            # request.path deliberately, never get_full_path(): query strings
            # carry search terms and tokens, and this table is not the place
            # for either.
            path=request.path[:MAX_PATH_LENGTH],
            method=request.method[:10],
            status_code=response.status_code,
            referrer=request.META.get("HTTP_REFERER", "")[:MAX_REFERRER_LENGTH],
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:MAX_USER_AGENT_LENGTH],
            ip_hash=hash_ip(request),
            is_authenticated=is_authenticated,
        )
