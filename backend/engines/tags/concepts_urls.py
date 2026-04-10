"""
engines/tags/concepts_urls.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase L1 — Concept Pages URL routing.
Included at: /api/v1/concepts/

Routes:
  GET  /api/v1/concepts/         → list all concept pages (filterable by is_content_ready)
  GET  /api/v1/concepts/<slug>/  → concept detail (brief always; body when is_content_ready=True)
"""

from django.urls import path

from engines.tags.views import ConceptDetailView, ConceptListView

urlpatterns = [
    path("", ConceptListView.as_view(), name="concept-list"),
    path("<slug:slug>/", ConceptDetailView.as_view(), name="concept-detail"),
]
