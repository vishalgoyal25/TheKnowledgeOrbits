"""
Progress Service

Handles user progress computation.
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from django.utils import timezone

import structlog

from engines.userstate.models import UserEvent, UserProgress

if TYPE_CHECKING:
    from engines.auth.models import User

logger = structlog.get_logger(__name__)


class ProgressService:
    """Service for computing user progress metrics."""

    @staticmethod
    def get_or_create_progress(user: "User") -> UserProgress:
        """Get or create user progress record."""
        progress, created = UserProgress.objects.get_or_create(user=user)
        if created:
            logger.info("progress_record_created", user_email=user.email)
        return progress

    @staticmethod
    def update_progress(user: "User") -> UserProgress:
        """
        Update user progress from events.

        Computes:
        - total_articles_read
        - total_quizzes_taken
        - current_streak
        """
        progress = ProgressService.get_or_create_progress(user)

        # Count articles read
        articles_read = (
            UserEvent.objects.filter(user=user, event_type="article_read")
            .values("event_data__article_id")
            .distinct()
            .count()
        )

        # Count quizzes taken
        quizzes_taken = (
            UserEvent.objects.filter(user=user, event_type="quiz_completed")
            .values("event_data__quiz_id")
            .distinct()
            .count()
        )

        # Calculate streak
        streak = ProgressService._calculate_streak(user)

        # Update progress
        progress.total_articles_read = articles_read
        progress.total_quizzes_taken = quizzes_taken
        progress.current_streak = streak
        progress.save()

        logger.info("progress_updated", user_email=user.email)

        return progress

    @staticmethod
    def _calculate_streak(user: "User") -> int:
        """
        Calculate consecutive days active.

        Logic:
        - User is active if they have any event on a day
        - Count consecutive days from today backwards
        """
        today = timezone.now().date()
        streak = 0
        check_date = today

        for _ in range(365):  # Max 365 days
            day_start = datetime.combine(check_date, datetime.min.time())
            day_end = datetime.combine(check_date, datetime.max.time())

            has_activity = UserEvent.objects.filter(
                user=user, created_at__gte=day_start, created_at__lte=day_end
            ).exists()

            if has_activity:
                streak += 1
                check_date -= timedelta(days=1)
            else:
                break

        return streak

    @staticmethod
    def calculate_syllabus_coverage(user: "User") -> float:
        """
        Calculate syllabus coverage percentage.

        Logic:
        - Count unique topics user has interacted with
        - Divide by total topics in knowledge engine
        - Return percentage
        """
        from engines.knowledge.models import Topic

        # Get topics user has mastery records for
        covered_topics = user.topic_masteries.values("topic_id").distinct().count()

        # Get total topics
        total_topics = Topic.objects.count()

        if total_topics == 0:
            return 0.0

        coverage = (covered_topics / total_topics) * 100

        # Update progress record
        progress = ProgressService.get_or_create_progress(user)
        progress.syllabus_coverage_percent = coverage
        progress.save()

        return coverage


# Singleton
_progress_service = None


def get_progress_service() -> ProgressService:
    """Get or create global progress service instance."""
    global _progress_service
    if _progress_service is None:
        _progress_service = ProgressService()
    return _progress_service
