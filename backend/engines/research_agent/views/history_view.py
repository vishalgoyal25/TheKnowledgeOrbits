"""
engines/research_agent/views/history_view.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GET /api/v1/research/history/          → paginated list of the user's sessions
GET /api/v1/research/history/<id>/     → one session + its report

History is for LOGGED-IN users only (guests get SSE-only, no DB history).
Uses select_related('report') + pagination → single query per page, no N+1
(Risk #23).

RBAC: IsAuthenticated. Each query is scoped to request.user, so a user can only
ever see their OWN sessions (ownership enforced by the queryset filter).
"""

from __future__ import annotations

import structlog
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from engines.research_agent.models.research_session import ResearchSession
from engines.research_agent.permissions import IsOwnerOrAdmin
from engines.research_agent.serializers.history_serializer import HistoryListSerializer
from engines.research_agent.serializers.session_serializer import (
    ResearchSessionSerializer,
)
from engines.research_agent.serializers.report_serializer import (
    ResearchReportSerializer,
)

logger = structlog.get_logger(__name__)


class _HistoryPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class HistoryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = (
            ResearchSession.objects.filter(user=request.user)
            .select_related("report")
            .order_by("-created_at")
        )
        paginator = _HistoryPagination()
        page = paginator.paginate_queryset(sessions, request, view=self)
        serializer = HistoryListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class HistoryDetailView(APIView):
    # Guests can fetch their own anonymous session by UUID (sources + confidence badge).
    # Authenticated users can only fetch sessions they own.
    permission_classes = [IsOwnerOrAdmin]

    def get(self, request, session_id: str):
        user = request.user
        if user.is_authenticated:
            session = (
                ResearchSession.objects.filter(id=session_id, user=user)
                .select_related("report")
                .first()
            )
        else:
            # Guest: allow read-only access to anonymous-owned sessions by UUID.
            session = (
                ResearchSession.objects.filter(id=session_id, user__isnull=True)
                .select_related("report")
                .first()
            )

        if session is None:
            return Response({"detail": "Session not found."}, status=404)

        data = ResearchSessionSerializer(session).data
        report = getattr(session, "report", None)
        data["report"] = (
            ResearchReportSerializer(report).data if report is not None else None
        )
        return Response(data, status=200)
