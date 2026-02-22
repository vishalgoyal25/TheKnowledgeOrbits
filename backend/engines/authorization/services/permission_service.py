"""
Permission Service

Centralized permission checking logic.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)


class PermissionService:
    """Service for checking user permissions."""

    @staticmethod
    def has_role(user, role_name: str) -> bool:
        """
        Check if user has specific role.

        Args:
            user: User instance
            role_name: Role name to check

        Returns:
            bool: True if user has role
        """
        if not user or not user.is_authenticated:
            return False

        return user.role_assignments.filter(role__name=role_name).exists()

    @staticmethod
    def has_any_role(user, role_names: List[str]) -> bool:
        """
        Check if user has any of the specified roles.

        Args:
            user: User instance
            role_names: List of role names

        Returns:
            bool: True if user has at least one role
        """
        if not user or not user.is_authenticated:
            return False

        return user.role_assignments.filter(role__name__in=role_names).exists()

    @staticmethod
    def get_user_roles(user) -> List[str]:
        """
        Get list of user's role names.

        Args:
            user: User instance

        Returns:
            List of role names
        """
        if not user or not user.is_authenticated:
            return []

        return list(user.role_assignments.values_list("role__name", flat=True))

    @staticmethod
    def can_manage_content(user) -> bool:
        """Check if user can manage content (upload, edit, delete)."""
        return PermissionService.has_any_role(user, ["admin", "content_manager"])

    @staticmethod
    def can_generate_quiz(user) -> bool:
        """Check if user can generate quizzes."""
        return PermissionService.has_any_role(user, ["admin", "content_manager"])

    @staticmethod
    def can_generate_article(user) -> bool:
        """Check if user can generate articles."""
        return PermissionService.has_any_role(user, ["admin", "content_manager"])

    @staticmethod
    def can_manage_roles(user) -> bool:
        """Check if user can manage roles (admin only)."""
        return PermissionService.has_role(user, "admin")

    @staticmethod
    def can_view_all_users(user) -> bool:
        """Check if user can view all users (admin only)."""
        return PermissionService.has_role(user, "admin")


# Singleton
_permission_service = None


def get_permission_service() -> PermissionService:
    """Get or create global permission service instance."""
    global _permission_service
    if _permission_service is None:
        _permission_service = PermissionService()
    return _permission_service
