"""
Authorization Engine - Role-Based Decorators

Provides function decorators for role checking.
"""

from functools import wraps
from typing import Any

from rest_framework import status
from rest_framework.response import Response


def require_role(*required_roles) -> Any:  # type: ignore
    """
    Decorator: Require user to have one of the specified roles.

    Usage:
        @require_role('admin', 'content_manager')
        def my_view(request):
            ...
    """

    def decorator(view_func) -> Any:  # type: ignore
        @wraps(view_func)
        def wrapper(request, *args, **kwargs) -> Any:  # type: ignore
            if not request.user or not request.user.is_authenticated:
                return Response(
                    {"error": "AUTHENTICATION_REQUIRED"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            # Check if user has any of the required roles
            user_roles = set(
                request.user.role_assignments.values_list("role__name", flat=True)
            )

            if not any(role in user_roles for role in required_roles):
                return Response(
                    {
                        "error": "PERMISSION_DENIED",
                        "message": f"Required role: {', '.join(required_roles)}",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def admin_only(view_func) -> Any:  # type: ignore
    """
    Decorator: Require admin role.

    Usage:
        @admin_only
        def my_view(request):
            ...
    """
    return require_role("admin")(view_func)


def content_manager_or_admin(view_func) -> Any:  # type: ignore
    """
    Decorator: Require content_manager or admin role.

    Usage:
        @content_manager_or_admin
        def my_view(request):
            ...
    """
    return require_role("admin", "content_manager")(view_func)
