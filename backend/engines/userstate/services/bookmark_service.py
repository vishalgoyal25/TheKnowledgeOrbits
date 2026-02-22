"""
Bookmark Service

Handles bookmark CRUD operations.
"""

import logging
from typing import List, Optional
from django.db import transaction

from engines.userstate.models import Bookmark
from engines.userstate.services.activity_service import get_activity_service

logger = logging.getLogger(__name__)


class BookmarkService:
    """Service for managing user bookmarks."""

    @staticmethod
    @transaction.atomic
    def add_bookmark(
        user, content_type: str, content_id: str, notes: str = ""
    ) -> Bookmark:
        """
        Add bookmark.

        Args:
            user: User instance
            content_type: 'article', 'quiz', or 'chunk'
            content_id: UUID of content
            notes: Optional notes

        Returns:
            Bookmark instance

        Raises:
            ValueError: If already bookmarked or invalid type
        """
        # Validate content type
        valid_types = ["article", "quiz", "chunk"]
        if content_type not in valid_types:
            raise ValueError(f"Invalid content_type. Must be one of: {valid_types}")

        # Check if already bookmarked
        if Bookmark.objects.filter(
            user=user, content_type=content_type, content_id=content_id
        ).exists():
            raise ValueError("Content already bookmarked")

        # Create bookmark
        bookmark = Bookmark.objects.create(
            user=user, content_type=content_type, content_id=content_id, notes=notes
        )

        # Log event
        activity_service = get_activity_service()
        activity_service.log_bookmark_added(user, content_type, content_id)

        logger.info(f"Bookmark added: {user.email} - {content_type}:{content_id}")

        return bookmark

    @staticmethod
    @transaction.atomic
    def remove_bookmark(user, bookmark_id: str) -> bool:
        """
        Remove bookmark.

        Args:
            user: User instance
            bookmark_id: Bookmark UUID

        Returns:
            bool: True if removed

        Raises:
            ValueError: If bookmark not found
        """
        try:
            bookmark = Bookmark.objects.get(id=bookmark_id, user=user)

            content_type = bookmark.content_type
            content_id = bookmark.content_id

            bookmark.delete()

            # Log event
            activity_service = get_activity_service()
            activity_service.log_bookmark_removed(user, content_type, str(content_id))

            logger.info(f"Bookmark removed: {user.email} - {bookmark_id}")

            return True

        except Bookmark.DoesNotExist:
            raise ValueError("Bookmark not found or not owned by you")

    @staticmethod
    def get_bookmarks(user, content_type: Optional[str] = None) -> List[Bookmark]:
        """
        Get user's bookmarks.

        Args:
            user: User instance
            content_type: Optional filter

        Returns:
            List of Bookmark instances
        """
        queryset = Bookmark.objects.filter(user=user)

        if content_type:
            if content_type not in ["article", "quiz", "chunk"]:
                raise ValueError("Invalid content_type")
            queryset = queryset.filter(content_type=content_type)

        return list(queryset.order_by("-created_at"))

    @staticmethod
    def is_bookmarked(user, content_type: str, content_id: str) -> bool:
        """Check if content is bookmarked."""
        return Bookmark.objects.filter(
            user=user, content_type=content_type, content_id=content_id
        ).exists()


# Singleton
_bookmark_service = None


def get_bookmark_service() -> BookmarkService:
    """Get or create global bookmark service instance."""
    global _bookmark_service
    if _bookmark_service is None:
        _bookmark_service = BookmarkService()
    return _bookmark_service
