"""
engines/research_agent/views/query_view.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
POST /api/v1/research/query/

Validates the query → creates a ResearchSession → queues the Celery task →
returns {session_id, stream_url} in <0.5s. The actual 30-90s workflow runs in
the worker, never here (Risk #1).

RBAC (Phase 5): AllowAny — public users are allowed. The per-day rate limiter
for anonymous users is a Phase 6 layer (middleware/rate_limiter.py).
"""

from __future__ import annotations

import hashlib

import structlog
import sentry_sdk
from django.utils import timezone
from datetime import timedelta
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from engines.research_agent.constants import SessionStatus
from engines.research_agent.models.research_session import ResearchSession
from engines.research_agent.serializers.session_serializer import QuerySubmitSerializer

logger = structlog.get_logger(__name__)

# Idempotency window: an identical query from the same identity within this many
# seconds returns the EXISTING in-flight session instead of starting a duplicate
# (Risk #41 — guards against double-submit / impatient retaps).
_IDEMPOTENCY_WINDOW_SECONDS = 30


class QueryView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = QuerySubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        query = serializer.validated_data["query"].strip()

        query_hash = hashlib.sha256(query.lower().encode("utf-8")).hexdigest()
        user = request.user if request.user.is_authenticated else None
        ip = self._client_ip(request)

        # ── Idempotency: reuse a very recent identical in-flight session ──────
        # (checked BEFORE the rate limit so a double-tap doesn't burn quota)
        existing = self._recent_inflight(query_hash, user, ip)
        if existing is not None:
            logger.info(
                "research_agent.query.idempotent_hit", session_id=str(existing.id)
            )
            return Response(self._payload(existing), status=200)

        # ── Cache hit (Opt #4): identical query → return report instantly, ────
        # zero LLM tokens, no pipeline, no quota consumed.
        from engines.research_agent.services.cache_service import cache_service

        cached = cache_service.get(query_hash)
        if cached is not None:
            # The cached blob may carry no confidence_score — either it predates
            # the back-fill, or DeepEval hadn't scored yet when it was cached.
            # Resolve it from the DB (system of record) so the badge renders, and
            # patch the cache so subsequent hits are instant.
            if cached.get("confidence_score") is None:
                score = self._confidence_from_db(query_hash)
                if score is not None:
                    cached["confidence_score"] = score
                    cache_service.patch_confidence(query_hash, score)
            return Response(
                {"cached": True, "status": "completed", "report": cached},
                status=200,
            )

        # ── Daily quota (Risk #2): anon = PUBLIC_DAILY_LIMIT, authed = AUTH_DAILY_LIMIT ──
        from engines.research_agent.middleware.rate_limiter import rate_limiter

        allowed, remaining = rate_limiter.check_query_limit(
            ip, user is not None, user_id=str(user.id) if user else None
        )
        if not allowed:
            logger.info(
                "research_agent.query.rate_limited",
                authenticated=user is not None,
                ip=ip,
            )
            if user is not None:
                message = (
                    "You've reached your daily limit of 10 research queries. "
                    "Thanks for researching with us — please try again after 24 hours. 🙏"
                )
            else:
                message = (
                    "You've used your free research queries for today. "
                    "Sign in for a higher daily limit, or try again after 24 hours. 🙏"
                )
            return Response({"detail": message, "remaining": 0}, status=429)

        try:
            session = ResearchSession.objects.create(
                user=user,
                query=query,
                query_hash=query_hash,
                ip_address=ip,
                status=SessionStatus.PENDING,
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error("research_agent.query.create_failed", error=str(exc))
            return Response({"detail": "Could not start research."}, status=500)

        # ── Queue the workflow on the background worker (off the request thread) ──
        from engines.research_agent.tasks.research_task import run_research

        run_research(str(session.id))

        logger.info(
            "research_agent.query.queued",
            session_id=str(session.id),
            authenticated=user is not None,
        )
        return Response(self._payload(session), status=202)

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────────────────────────────────
    def _confidence_from_db(self, query_hash: str) -> float | None:
        """
        Latest completed report's confidence_score for this query (the system of
        record). Used to back-fill a cache hit whose blob lacks the score.
        Defensive — any lookup failure returns None (badge stays in pending).
        """
        try:
            session = (
                ResearchSession.objects.filter(
                    query_hash=query_hash, status=SessionStatus.COMPLETED
                )
                .select_related("report")
                .order_by("-created_at")
                .first()
            )
            report = getattr(session, "report", None) if session else None
            return getattr(report, "confidence_score", None) if report else None
        except Exception:
            return None

    def _recent_inflight(self, query_hash: str, user, ip: str | None):
        """Return a pending/running session for the same query + identity, if recent."""
        cutoff = timezone.now() - timedelta(seconds=_IDEMPOTENCY_WINDOW_SECONDS)
        qs = ResearchSession.objects.filter(
            query_hash=query_hash,
            status__in=[SessionStatus.PENDING, SessionStatus.RUNNING],
            created_at__gte=cutoff,
        )
        qs = (
            qs.filter(user=user)
            if user is not None
            else qs.filter(user__isnull=True, ip_address=ip)
        )
        return qs.order_by("-created_at").first()

    @staticmethod
    def _client_ip(request) -> str | None:
        """Real client IP — X-Forwarded-For aware (Render load balancer, Risk #34/#38)."""
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

    @staticmethod
    def _payload(session: ResearchSession) -> dict:
        return {
            "session_id": str(session.id),
            "status": session.status,
            "stream_url": f"/api/v1/research/stream/{session.id}/",
        }
