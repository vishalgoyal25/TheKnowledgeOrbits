"""
Authorization Engine - RBAC Middleware

Attaches user roles to request object for easy access.
Roles are cached in Redis for 5 minutes per user to avoid a DB JOIN on every
authenticated request (was firing 1 query/request at 80ms RTT on Render→Supabase).
"""

from typing import Any

from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin

# Cache TTL for user role lookups — role changes propagate within 5 minutes.
_ROLE_CACHE_TTL = 300  # seconds


class RBACMiddleware(MiddlewareMixin):
    """
    Middleware to attach user roles to request.

    After this middleware, you can access:
        - request.user_roles (list of role names)
        - request.is_admin (boolean)
        - request.is_content_manager (boolean)
    """

    def process_request(self, request) -> Any:  # type: ignore
        """Attach role information to request."""

        if hasattr(request, "user") and request.user.is_authenticated:
            # Check Redis cache first — avoids a DB JOIN on every request
            cache_key = f"user_roles_{request.user.id}"
            user_roles = cache.get(cache_key)

            if user_roles is None:
                user_roles = list(
                    request.user.role_assignments.values_list("role__name", flat=True)
                )
                cache.set(cache_key, user_roles, timeout=_ROLE_CACHE_TTL)

            # Attach to request
            request.user_roles = user_roles
            request.is_admin = "admin" in user_roles
            request.is_content_manager = "content_manager" in user_roles
            request.is_student = "student" in user_roles
            request.is_free_user = "free_user" in user_roles
        else:
            # Anonymous user
            request.user_roles = []
            request.is_admin = False
            request.is_content_manager = False
            request.is_student = False
            request.is_free_user = False

        return None
