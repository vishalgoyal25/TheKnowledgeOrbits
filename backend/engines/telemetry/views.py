"""
Telemetry Engine Views — the public read beacon.

POST /api/v1/telemetry/read/

Why this endpoint exists
────────────────────────
Public pages are ISR-cached on Vercel's CDN, so a reader never reaches Django
and the request middleware never sees them. A page read 5,000 times and one
read twice would produce identical VisitLog rows. This beacon is fired from
the article page on mount, which is the only way to count actual readership.

It is a POST, so it is immune to every caching layer between the reader and
Django — the CDN, the browser cache, and the Cache-Control headers set in
core/middleware.py.
"""

from __future__ import annotations

import structlog
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status, views
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from engines.telemetry.models import ContentRead
from engines.telemetry.serializers import ContentReadSerializer
from engines.telemetry.utils import hash_ip, is_enabled, report, within_rate_limit

logger = structlog.get_logger(__name__)


class ContentReadBeaconView(views.APIView):
    """
    Records that a piece of content was read. One row per reader, per item,
    per day — enforced by the database, not by this view.
    """

    # ⚠️ MANDATORY. The project default is IsAuthenticatedOrReadOnly
    # (core/settings/base.py), under which this POST returns 403 to every
    # ANONYMOUS reader while working perfectly for a signed-in developer.
    # Without this line the table fills with authenticated traffic only, looks
    # plausible, and is systematically wrong. Do not remove it.
    permission_classes = [AllowAny]

    # This endpoint is the project's only unauthenticated write surface.
    # Everything it accepts is bounded by ContentReadSerializer; everything
    # identifying is derived here, never taken from the caller.
    def post(self, request: Request) -> Response:
        # Kill switch. Also false when TELEMETRY_IP_SALT is unset (fail safe).
        # Answer 204 rather than an error: whether telemetry is running is not
        # the caller's concern, and a reader must never see a failure from it.
        if not is_enabled():
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = ContentReadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Salted hash, X-Forwarded-For aware. Doubles as the rate-limit key, so
        # no raw IP ever reaches Redis either.
        ip_hash = hash_ip(request)

        # Limit AFTER validation: only well-formed requests can actually write
        # a row, so those are the ones worth throttling. Fails open if Redis is
        # down — see utils.within_rate_limit.
        if not within_rate_limit(ip_hash):
            logger.info("telemetry_beacon_rate_limited")
            return Response(status=status.HTTP_429_TOO_MANY_REQUESTS)

        user = getattr(request, "user", None)
        is_authenticated = bool(user is not None and user.is_authenticated)

        try:
            # transaction.atomic() is REQUIRED, not decoration: a raised
            # IntegrityError marks the surrounding transaction as needing
            # rollback, and every later query on the connection would fail with
            # "current transaction is aborted". The savepoint confines it.
            with transaction.atomic():
                # No .using() — `default` is Supabase in production.
                ContentRead.objects.create(
                    content_type=serializer.validated_data["content_type"],
                    content_id=serializer.validated_data["content_id"],
                    ip_hash=ip_hash,
                    is_authenticated=is_authenticated,
                    read_date=timezone.localdate(),
                )
        except IntegrityError:
            # The unique constraint fired: this reader already counted for this
            # item today. That is the dedupe working as designed, so it is a
            # SUCCESS, not an error — a refresh must not inflate counts, and it
            # must not look like a failure to the page either.
            pass
        except Exception as exc:  # noqa: BLE001
            # Telemetry must never surface a failure to a reader. Report it and
            # answer 204 anyway; the page is not broken because a count was not
            # recorded.
            report(exc)
            logger.warning("telemetry_beacon_write_failed", error=str(exc)[:200])

        return Response(status=status.HTTP_204_NO_CONTENT)
