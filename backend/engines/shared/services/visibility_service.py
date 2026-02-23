"""
Visibility Service

Filters content based on ownership and public/private status.
"""

from typing import TYPE_CHECKING, Any, Optional

from django.db.models import Q, QuerySet

import structlog

if TYPE_CHECKING:
    from engines.auth.models import User

logger = structlog.get_logger(__name__)


class VisibilityService:
    """Service for filtering content by visibility rules."""

    @staticmethod
    def filter_articles(queryset: QuerySet, user: Optional["User"] = None) -> QuerySet:  # type: ignore
        """
        Filter articles based on visibility.

        Rules:
        - Public articles (is_public=True): visible to all
        - Private articles (is_public=False): visible only to owner
        - Anonymous users: see only public
        - Logged-in users: see public + own private

        Args:
            queryset: Article queryset
            user: Current user (None if anonymous)

        Returns:
            Filtered queryset
        """
        if user and user.is_authenticated:
            # Logged-in: public OR owned by user
            return queryset.filter(Q(is_public=True) | Q(created_by=user))
        else:
            # Anonymous: public only
            return queryset.filter(is_public=True)

    @staticmethod
    def filter_quizzes(queryset: QuerySet, user: Optional["User"] = None) -> QuerySet:  # type: ignore
        """
        Filter quizzes based on visibility.

        Same rules as articles.
        """
        if user and user.is_authenticated:
            return queryset.filter(Q(is_public=True) | Q(created_by=user))
        else:
            return queryset.filter(is_public=True)

    @staticmethod
    def can_access_article(article: Any, user: Optional["User"] = None) -> bool:
        """
        Check if user can access specific article.

        Args:
            article: Article instance
            user: Current user (None if anonymous)

        Returns:
            bool: True if user can access
        """
        # Public articles accessible to all
        if article.is_public:
            return True

        # Private articles only accessible to owner
        if user and user.is_authenticated and article.created_by == user:
            return True

        return False

    @staticmethod
    def can_access_quiz(quiz: Any, user: Optional["User"] = None) -> bool:
        """
        Check if user can access specific quiz.

        Same logic as articles.
        """
        if quiz.is_public:
            return True

        if user and user.is_authenticated and quiz.created_by == user:
            return True

        return False


# Singleton
_visibility_service = None


def get_visibility_service() -> VisibilityService:
    """Get or create global visibility service instance."""
    global _visibility_service
    if _visibility_service is None:
        _visibility_service = VisibilityService()
    return _visibility_service
