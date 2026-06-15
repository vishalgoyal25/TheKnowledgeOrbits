"""
engines/research_agent/views/stream_view.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GET /api/v1/research/stream/<session_id>/

Server-Sent Events endpoint. Returns a StreamingHttpResponse whose body is the
generator from sse_service.stream() — live events bridged from the background
worker through Redis pub/sub. Heartbeat every 15s keeps proxies from closing it.

Uses a PLAIN Django View (not DRF APIView): DRF runs content negotiation and
response processing that interferes with long-lived streaming responses. SSE
endpoints must be plain Django views.

IMPORTANT (Risk #12): the frontend must hit this DIRECTLY on the Render backend
URL — never through Vercel, which buffers responses and breaks SSE.
"""

from __future__ import annotations

import structlog
from django.http import StreamingHttpResponse, JsonResponse
from django.views import View

from engines.research_agent.constants import SessionStatus
from engines.research_agent.models.research_session import ResearchSession
from engines.research_agent.services.sse_service import sse_service

logger = structlog.get_logger(__name__)

_TERMINAL_STATUSES = (
    SessionStatus.COMPLETED,
    SessionStatus.FAILED,
    SessionStatus.CANCELLED,
)


class StreamView(View):
    def get(self, request, session_id: str):
        session = ResearchSession.objects.filter(id=session_id).only("status").first()
        if session is None:
            return JsonResponse({"detail": "Session not found."}, status=404)

        logger.info(
            "research_agent.stream.opened", session_id=session_id, status=session.status
        )

        # If the session already finished, don't subscribe to a dead Redis
        # channel (would heartbeat forever) — emit the final event and close.
        if session.status in _TERMINAL_STATUSES:
            generator = sse_service.terminal_stream(session.status)
        else:
            generator = sse_service.stream(session_id)

        response = StreamingHttpResponse(
            generator,
            content_type="text/event-stream",
        )
        # SSE-critical headers. NOTE: 'Connection: keep-alive' is a hop-by-hop
        # header — WSGI forbids setting it manually (the server manages it), so
        # we do NOT set it here.
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"  # disable nginx/proxy buffering
        response["Access-Control-Allow-Origin"] = "*"  # CORS on the stream (Risk #51)
        return response
