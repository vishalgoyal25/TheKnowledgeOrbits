"""
engines/daily_ca/urls.py
━━━━━━━━━━━━━━━━━━━━━━━━
Phase L2 — Daily CA public API URL routing.
Included at: /api/v1/daily-ca/

Routes:
  GET /api/v1/daily-ca/today/              → today's published articles (cached)
  GET /api/v1/daily-ca/archive/            → last 30 days, date-grouped
  GET /api/v1/daily-ca/article/<slug>/     → full article detail
  GET /api/v1/daily-ca/<date>/             → articles for specific date (YYYY-MM-DD)

Note: 'today' and 'archive' must come before '<date_str>' to avoid slug conflict.
"""

from django.urls import path

from engines.daily_ca.views import ArchiveView, ArticleDetailView, DateView, TodayView

urlpatterns = [
    path("today/", TodayView.as_view(), name="daily-ca-today"),
    path("archive/", ArchiveView.as_view(), name="daily-ca-archive"),
    path("article/<slug:slug>/", ArticleDetailView.as_view(), name="daily-ca-article-detail"),
    path("<str:date_str>/", DateView.as_view(), name="daily-ca-date"),
]
