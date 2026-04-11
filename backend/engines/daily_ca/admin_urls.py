"""
engines/daily_ca/admin_urls.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase L3 — Daily CA admin API URL routing.
Included at: /api/v1/admin/daily-ca/

No authentication — solo developer, direct access from frontend UI.

Routes:
  GET  /api/v1/admin/daily-ca/proposals/<date>/     → list proposals for review
  POST /api/v1/admin/daily-ca/proposals/approve/    → approve selected IDs (max 10)
  GET  /api/v1/admin/daily-ca/generate/status/      → status breakdown for a date
  POST /api/v1/admin/daily-ca/publish/<date>/       → publish all generated articles
  GET  /api/v1/admin/daily-ca/articles/<date>/      → all articles for date (incl. unpublished)
"""

from django.urls import path

from engines.daily_ca.views import (
    AdminApproveView,
    AdminArticlesDateView,
    AdminGenerateStatusView,
    AdminProposalListView,
    AdminPublishDateView,
)

urlpatterns = [
    path(
        "proposals/approve/", AdminApproveView.as_view(), name="admin-proposals-approve"
    ),
    path(
        "proposals/<str:date_str>/",
        AdminProposalListView.as_view(),
        name="admin-proposals-list",
    ),
    path(
        "generate/status/",
        AdminGenerateStatusView.as_view(),
        name="admin-generate-status",
    ),
    path(
        "publish/<str:date_str>/",
        AdminPublishDateView.as_view(),
        name="admin-publish-date",
    ),
    path(
        "articles/<str:date_str>/",
        AdminArticlesDateView.as_view(),
        name="admin-articles-date",
    ),
]
