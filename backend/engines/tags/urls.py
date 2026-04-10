"""
engines/tags/urls.py
━━━━━━━━━━━━━━━━━━━━
Phase L1 — Tags Engine URL routing.
Included at: /api/v1/tags/

Routes:
  GET  /api/v1/tags/                  → list all active tags (filterable by type)
  GET  /api/v1/tags/<slug>/           → tag detail + recent articles
  GET  /api/v1/tags/<slug>/articles/  → all published DailyCaArticles for this tag
"""

from django.urls import path

from engines.tags.views import TagArticlesView, TagDetailView, TagListView

urlpatterns = [
    path("", TagListView.as_view(), name="tag-list"),
    path("<slug:slug>/", TagDetailView.as_view(), name="tag-detail"),
    path("<slug:slug>/articles/", TagArticlesView.as_view(), name="tag-articles"),
]
