"""
engines/research_agent/urls.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Research Agent engine — URL routing. Included at: /api/v1/research/

  POST  /api/v1/research/query/                 → submit query (creates session)
  GET   /api/v1/research/stream/<session_id>/   → SSE stream (live agent events)
  POST  /api/v1/research/cancel/<session_id>/   → cancel a running session
  GET   /api/v1/research/history/               → user's past sessions (auth)
  GET   /api/v1/research/history/<session_id>/  → single session + report
  GET   /api/v1/research/export/<session_id>/   → export report (PDF/MD) — Phase 9
"""

from django.urls import path

from engines.research_agent.views import (
    QueryView,
    StreamView,
    CancelView,
    HistoryListView,
    HistoryDetailView,
    ExportView,
)

app_name = "research_agent"

urlpatterns: list = [
    path("query/", QueryView.as_view(), name="query"),
    path("stream/<str:session_id>/", StreamView.as_view(), name="stream"),
    path("cancel/<str:session_id>/", CancelView.as_view(), name="cancel"),
    path("history/", HistoryListView.as_view(), name="history-list"),
    path(
        "history/<str:session_id>/", HistoryDetailView.as_view(), name="history-detail"
    ),
    path("export/<str:session_id>/", ExportView.as_view(), name="export"),
]
