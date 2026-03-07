from typing import Any

from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse, JsonResponse
from django.urls import include, path


def health_check(request: Any) -> HttpResponse:
    """
    Ultra-lightweight health check for Render/LB.
    Returns plain text for maximum speed and zero overhead.
    """
    return HttpResponse("OK, System is Successfully Running!", status=200)


def api_index(request: Any) -> JsonResponse:
    """API Index with available modules (Plain Django for speed)."""
    return JsonResponse(
        {
            "name": "TheKnowledgeOrbits API",
            "version": "v1",
            "status": "online",
            "endpoints": {
                "health": "/api/v1/health/",
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
    path("", health_check, name="health-check"),
    path("api/v1/", api_index, name="api-index"),
    path("api/v1/health/", health_check, name="health-check-v1"),
    # Engine URLs
    path("api/v1/content/", include("engines.content.urls")),
    path("api/v1/knowledge/", include("engines.knowledge.urls")),
    path("api/v1/articles/", include("engines.article_generation.urls")),
    path("api/v1/ca/", include("engines.current_affairs.urls")),
    path("api/v1/assessment/", include("engines.assessment.urls")),
    path("api/v1/userstate/", include("engines.userstate.urls")),
    path("api/v1/analytics/", include("engines.analytics.urls")),
    path("api/v1/auth/", include("engines.auth.urls")),
    path("api/v1/authorization/", include("engines.authorization.urls")),
    path("api/v1/support/", include("engines.support.urls")),
]

# Conditionally add the admin path (not disabled in production)
if "django.contrib.admin" in settings.INSTALLED_APPS:
    urlpatterns.append(path("admin/", admin.site.urls))
