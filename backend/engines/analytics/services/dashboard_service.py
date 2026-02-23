"""
Dashboard Service

Assembles complete dashboard data from multiple sources.
"""

from typing import TYPE_CHECKING, Any, Dict

import structlog

from engines.analytics.services.analytics_service import get_analytics_service
from engines.analytics.services.insights_service import get_insights_service
from engines.userstate.models import TopicMastery, UserEvent
from engines.userstate.services.progress_service import get_progress_service

if TYPE_CHECKING:
    from engines.auth.models import User

logger = structlog.get_logger(__name__)


class DashboardService:
    """Service for assembling dashboard data."""

    @staticmethod
    def get_dashboard_overview(user: "User") -> Dict[str, Any]:
        """
        Get complete dashboard overview for user.

        Returns:
            dict: Complete dashboard data
        """
        # Get progress
        progress_service = get_progress_service()
        progress = progress_service.get_or_create_progress(user)

        # Get topic mastery
        masteries = TopicMastery.objects.filter(user=user).select_related("topic")

        # Get weak topics (< 50%)
        weak_topics = masteries.filter(
            mastery_score__lt=50, questions_attempted__gte=3
        ).order_by("mastery_score")[:5]

        # Get strong topics (>= 80%)
        strong_topics = masteries.filter(
            mastery_score__gte=80, questions_attempted__gte=5
        ).order_by("-mastery_score")[:5]

        # Get recent activity
        recent_events = UserEvent.objects.filter(user=user).order_by("-created_at")[:10]

        # Get analytics
        analytics_service = get_analytics_service()
        weekly_stats = analytics_service.get_weekly_stats(user)

        # Get insights
        insights_service = get_insights_service()
        active_insights = insights_service.get_active_insights(user)

        return {
            "overview": {
                "total_articles_read": progress.total_articles_read,
                "total_quizzes_taken": progress.total_quizzes_taken,
                "current_streak": progress.current_streak,
                "syllabus_coverage": progress.syllabus_coverage_percent,
            },
            "performance": {
                "weekly": weekly_stats,
                "topic_count": masteries.count(),
                "average_mastery": (
                    sum(m.mastery_score for m in masteries) / masteries.count()
                    if masteries.count() > 0
                    else 0
                ),
            },
            "topics": {
                "weak": [
                    {
                        "topic_id": str(m.topic.id),
                        "topic_name": m.topic.name,
                        "mastery_score": m.mastery_score,
                        "questions_attempted": m.questions_attempted,
                    }
                    for m in weak_topics
                ],
                "strong": [
                    {
                        "topic_id": str(m.topic.id),
                        "topic_name": m.topic.name,
                        "mastery_score": m.mastery_score,
                        "questions_attempted": m.questions_attempted,
                    }
                    for m in strong_topics
                ],
            },
            "recent_activity": [
                {
                    "event_type": event.event_type,
                    "event_data": event.event_data,
                    "created_at": event.created_at.isoformat(),
                }
                for event in recent_events
            ],
            "insights": [
                {
                    "type": insight.insight_type,
                    "data": insight.insight_data,
                    "generated_at": insight.generated_at.isoformat(),
                }
                for insight in active_insights
            ],
        }


# Singleton
_dashboard_service = None


def get_dashboard_service() -> DashboardService:
    """Get or create global dashboard service instance."""
    global _dashboard_service
    if _dashboard_service is None:
        _dashboard_service = DashboardService()
    return _dashboard_service
