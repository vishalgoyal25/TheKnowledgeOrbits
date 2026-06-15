"""
engines/research_agent/views/cancel_view.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
POST /api/v1/research/cancel/<session_id>/

Sets the Redis cancel flag for the session. Every agent checks this flag as the
FIRST thing it does (BaseAgent.run step 1), so the running workflow stops
wasting LLM budget within one node (Risk #12/#36). Also emits a
workflow_cancelled SSE event so the browser updates immediately.

Called by the frontend on the Cancel button AND via navigator.sendBeacon() on
tab close (Phase 11).

RBAC (Phase 5): AllowAny — the session UUID is the capability token.
"""

from __future__ import annotations

import structlog
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from engines.research_agent.constants import SSEEvent, SessionStatus
from engines.research_agent.models.research_session import ResearchSession
from engines.research_agent.services.sse_service import sse_service

logger = structlog.get_logger(__name__)


class CancelView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, session_id: str):
        session = ResearchSession.objects.filter(id=session_id).first()
        if session is None:
            return Response({"detail": "Session not found."}, status=404)

        # Already finished → nothing to cancel.
        if session.status in (
            SessionStatus.COMPLETED,
            SessionStatus.FAILED,
            SessionStatus.CANCELLED,
        ):
            return Response(
                {"status": session.status, "detail": "Session already finished."},
                status=200,
            )

        # 1) Redis flag → agents stop between nodes.
        sse_service.set_cancelled(session_id)
        # 2) DB status.
        session.mark_cancelled()
        # 3) Tell the browser immediately.
        sse_service.emit(
            session_id, SSEEvent.WORKFLOW_CANCELLED, {"reason": "user_cancelled"}
        )

        logger.info("research_agent.cancel.requested", session_id=session_id)
        return Response({"status": SessionStatus.CANCELLED}, status=200)
