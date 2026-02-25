"""
URL configuration for TheKnowledgeOrbits.
"""

from typing import Any

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health_check(request: Any) -> JsonResponse:
    """
    Ultra-lightweight health check for Render/LB.
    Does NOT check DB to avoid connection pool exhaustion
    and 5s timeout failures during heavy DB load.
    """
    return JsonResponse(
        {
            "status": "healthy",
            "message": "TheKnowledgeOrbits API is operational",
        },
        status=200,
    )


def api_index(request: Any) -> JsonResponse:
    """API Index with available modules (Plain Django for speed)."""
    return JsonResponse(
        {
            "name": "TheKnowledgeOrbits API",
            "version": "v1",
            "status": "online",
            "endpoints": {
                "auth": "/api/v1/auth/",
                "content": "/api/v1/content/",
                "knowledge": "/api/v1/knowledge/",
                "articles": "/api/v1/articles/",
                "current_affairs": "/api/v1/ca/",
                "assessment": "/api/v1/assessment/",
                "user_state": "/api/v1/userstate/",
                "analytics": "/api/v1/analytics/",
                "authorization": "/api/v1/authorization/",
                "support": "/api/v1/support/",
            },
        },
        status=200,
    )


urlpatterns = [
    path("", api_index, name="api-index"),
    path("admin/", admin.site.urls),
    path("api/v1/health/", health_check, name="health-check"),
    # Engine URLs will be added here as we build them
    # Content Engine
    path("api/v1/content/", include("engines.content.urls")),
    # Knowledge Engine
    path("api/v1/knowledge/", include("engines.knowledge.urls")),
    # Article Generation Engine
    path("api/v1/articles/", include("engines.article_generation.urls")),
    # Current Affairs Engine
    path("api/v1/ca/", include("engines.current_affairs.urls")),
    # Assessment Engine
    path("api/v1/assessment/", include("engines.assessment.urls")),
    # User State Engine
    path("api/v1/userstate/", include("engines.userstate.urls")),
    # Analytics Engine
    path("api/v1/analytics/", include("engines.analytics.urls")),
    # Auth Engine
    path("api/v1/auth/", include("engines.auth.urls")),
    # Authorization Engine
    path("api/v1/authorization/", include("engines.authorization.urls")),
    # Support Engine
    path("api/v1/support/", include("engines.support.urls")),
]
