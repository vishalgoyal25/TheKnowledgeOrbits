"""
engines/research_agent/permissions.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RBAC permission classes for Research Agent endpoints.

Phase 5 wires the basic owner/public gates here. The per-day rate limit for
anonymous users (PUBLIC_DAILY_LIMIT) is enforced by the Redis-backed
middleware/rate_limiter.py in Phase 6 — not here.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOwnerOrAdmin(BasePermission):
    """
    Object-level: the session owner or a staff/admin may access.
    Anonymous-owned (public) sessions are readable by anyone holding the UUID.
    Used by history/export/detail endpoints.
    """

    def has_permission(self, request, view) -> bool:
        # List/create gating is handled by the view's queryset scoping;
        # object access is decided in has_object_permission.
        return True

    def has_object_permission(self, request, view, obj) -> bool:
        user = getattr(request, "user", None)

        # Staff/admin always allowed.
        if user is not None and user.is_authenticated and user.is_staff:
            return True

        # Owner of the session.
        owner_id = getattr(obj, "user_id", None)
        if owner_id is not None and user is not None and user.is_authenticated:
            return owner_id == user.id

        # Public (anonymous-owned) session: readable on safe methods.
        if owner_id is None and request.method in SAFE_METHODS:
            return True

        return False


class IsPublicOrAuthenticated(BasePermission):
    """
    Public users are allowed (the actual PUBLIC_DAILY_LIMIT throttle is the
    Phase 6 Redis rate limiter). Authenticated users always pass.
    Used by the query submission endpoint.
    """

    def has_permission(self, request, view) -> bool:
        return True
