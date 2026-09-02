"""
Telemetry Engine URLs

Mounted at /api/v1/telemetry/ from core/urls.py.

This prefix is also listed in the middleware's SKIP_PATH_PREFIXES — the beacon
must not generate a VisitLog row for itself, or every read would be recorded
twice: once as content, once as traffic about recording content.
"""

from django.urls import path

from engines.telemetry import views

app_name = "telemetry"

urlpatterns = [
    path(
        "read/",
        views.ContentReadBeaconView.as_view(),
        name="content-read-beacon",
    ),
]
