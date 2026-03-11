"""
WSGI config for TheKnowledgeOrbits.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.dev")


django_application = get_wsgi_application()


def application(environ, start_response):
    """
    WSGI wrapper to intercept health checks before they hit Django middleware.
    Ensures Render health checks never fail during cold boots.
    """
    path = environ.get("PATH_INFO", "")

    # 1. Lightweight Intercept (Fastest) - Prevents load balancer timeouts
    if path == "/api/v1/health/":
        status = "200 OK"
        response_headers = [("Content-type", "application/json")]
        start_response(status, response_headers)
        return [
            b'{"status": "ok", "message": "Ultra-lightweight WSGI health check passed"}'
        ]

    # 2. Deep Health Check - Pass through to Django to verify Database/Supabase
    # We explicitly do NOT intercept this here so it reaches the Django view
    if path == "/api/v1/health/deep/":
        return django_application(environ, start_response)

    # 3. Standard Application Traffic
    return django_application(environ, start_response)
