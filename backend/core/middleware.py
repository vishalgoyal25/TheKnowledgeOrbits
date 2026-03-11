"""
Core Middlewares for TheKnowledgeOrbits
"""

import re


class CacheControlMiddleware:
    """
    Adds Cache-Control headers to specific public endpoints
    to allow the Edge CDN (Vercel/Cloudflare) to instantly
    serve stale data while fetching fresh data async.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only apply to successful GET requests
        if request.method != "GET" or response.status_code != 200:
            return response

        # Do not cache authenticated user requests globally
        if (
            "Authorization" in request.headers
            or getattr(request, "user", None)
            and request.user.is_authenticated
        ):
            response["Cache-Control"] = "no-store, no-cache, private"
            return response

        # Target public APIs that benefit from ISR/CDN caching
        path = request.path
        public_api_pattern = (
            r"^/api/v1/(current-affairs|articles|knowledge|topics|subjects)/"
        )

        if re.match(public_api_pattern, path):
            if "Cache-Control" not in response:
                # Cache at Edge for 60s of stale data while revalidating
                response["Cache-Control"] = (
                    "public, max-age=15, stale-while-revalidate=60"
                )

        return response
