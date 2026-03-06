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
    if environ.get("PATH_INFO", "") == "/api/v1/health/":
        status = "200 OK"
        response_headers = [("Content-type", "application/json")]
        start_response(status, response_headers)
        return [
            b'{"status": "ok", "message": "Ultra-lightweight WSGI health check passed"}'
        ]

    return django_application(environ, start_response)
