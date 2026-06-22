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

        # Daily CA — articles change once per day at publish time
        if re.match(r"^/api/v1/daily-ca/\d{4}-\d{2}-\d{2}/", path):
            # Past-date articles are immutable — cache aggressively
            response["Cache-Control"] = (
                "public, max-age=3600, stale-while-revalidate=300"
            )
            return response

        if re.match(r"^/api/v1/daily-ca/today/", path):
            response["Cache-Control"] = "public, max-age=300, stale-while-revalidate=60"
            return response

        if re.match(r"^/api/v1/daily-ca/archive/", path):
            response["Cache-Control"] = "public, max-age=300, stale-while-revalidate=60"
            return response

        if re.match(r"^/api/v1/daily-ca/article/", path):
            # Article detail — immutable after publish
            response["Cache-Control"] = (
                "public, max-age=3600, stale-while-revalidate=300"
            )
            return response

        # Book content — changes only when new topics/content generated
        if re.match(r"^/api/v1/book/(subjects|tree|graph)/", path):
            response["Cache-Control"] = (
                "public, max-age=3600, stale-while-revalidate=300"
            )
            return response

        # Tags & concepts — slow-changing
        if re.match(r"^/api/v1/(tags|concepts)/", path):
            response["Cache-Control"] = (
                "public, max-age=3600, stale-while-revalidate=300"
            )
            return response

        # Original pattern — existing endpoints
        #
        # NOTE: 'articles' is intentionally EXCLUDED here. The article_generation
        # endpoints return user-specific content — a logged-in user additionally
        # sees their own private (is_public=False) articles. Marking them
        # `public` lets the edge CDN cache an ANONYMOUS response keyed by URL
        # only (no Vary on Authorization) and then serve that stale anonymous
        # copy to authenticated users. The article UI reads it as "not logged
        # in" and bounces the user to the login page in a loop. Quiz endpoints
        # are never cached, which is exactly why the quiz flow has no such issue.
        # Authenticated requests are already protected above (no-store); the
        # only safe fix for the shared-URL anonymous cache is to not mark these
        # responses public at all.
        public_api_pattern = r"^/api/v1/(current-affairs|knowledge|topics|subjects)/"

        if re.match(public_api_pattern, path):
            if "Cache-Control" not in response:
                # Cache at Edge for 60s of stale data while revalidating
                response["Cache-Control"] = (
                    "public, max-age=15, stale-while-revalidate=60"
                )

        return response
