"""
Activity Service

Handles event logging (event sourcing pattern).
"""

import logging
from typing import Dict, Any, Optional
from engines.userstate.models import UserEvent

logger = logging.getLogger(__name__)


class ActivityService:
    """Service for tracking user activities via events."""

    @staticmethod
    def log_event(
        user, event_type: str, event_data: Optional[Dict[str, Any]] = None
    ) -> UserEvent:
        """
        Log a user event.

        Args:
            user: User instance
            event_type: Event type (see UserEvent.EVENT_TYPE_CHOICES)
            event_data: Additional metadata

        Returns:
            UserEvent instance
        """
        event = UserEvent.objects.create(
            user=user, event_type=event_type, event_data=event_data or {}
        )

        logger.debug(f"Event logged: {user.email} - {event_type}")

        return event

    # Convenience methods for common events

    @staticmethod
    def log_article_read(user, article_id: str):
        """Log article read event."""
        return ActivityService.log_event(
            user=user,
            event_type="article_read",
            event_data={"article_id": str(article_id)},
        )

    @staticmethod
    def log_article_generated(user, article_id: str, topic_id: str):
        """Log article generation event."""
        return ActivityService.log_event(
            user=user,
            event_type="article_generated",
            event_data={"article_id": str(article_id), "topic_id": str(topic_id)},
        )

    @staticmethod
    def log_quiz_started(user, quiz_id: str, attempt_id: str):
        """Log quiz start event."""
        return ActivityService.log_event(
            user=user,
            event_type="quiz_started",
            event_data={"quiz_id": str(quiz_id), "attempt_id": str(attempt_id)},
        )

    @staticmethod
    def log_quiz_completed(user, quiz_id: str, attempt_id: str, score: float):
        """Log quiz completion event."""
        return ActivityService.log_event(
            user=user,
            event_type="quiz_completed",
            event_data={
                "quiz_id": str(quiz_id),
                "attempt_id": str(attempt_id),
                "score": score,
            },
        )

    @staticmethod
    def log_bookmark_added(user, content_type: str, content_id: str):
        """Log bookmark addition."""
        return ActivityService.log_event(
            user=user,
            event_type="bookmark_added",
            event_data={"content_type": content_type, "content_id": str(content_id)},
        )

    @staticmethod
    def log_bookmark_removed(user, content_type: str, content_id: str):
        """Log bookmark removal."""
        return ActivityService.log_event(
            user=user,
            event_type="bookmark_removed",
            event_data={"content_type": content_type, "content_id": str(content_id)},
        )


# Singleton
_activity_service = None


def get_activity_service() -> ActivityService:
    """Get or create global activity service instance."""
    global _activity_service
    if _activity_service is None:
        _activity_service = ActivityService()
    return _activity_service
