"""
Insights Service

Generates actionable insights for users.
"""

import logging
from datetime import timedelta
from django.utils import timezone

from django.db import models
from engines.analytics.models import Insight
from engines.userstate.models import TopicMastery, UserEvent
from engines.userstate.services.progress_service import get_progress_service

logger = logging.getLogger(__name__)


class InsightsService:
    """Service for generating user insights."""

    @staticmethod
    def generate_insights(user):
        """
        Generate all types of insights for user.

        Returns:
            list: List of generated insights
        """
        insights = []

        # Generate weak topic insights
        insights.extend(InsightsService._generate_weak_topic_insights(user))

        # Generate streak risk insights
        insights.extend(InsightsService._generate_streak_insights(user))

        # Generate improvement insights
        insights.extend(InsightsService._generate_improvement_insights(user))

        # Generate milestone insights
        insights.extend(InsightsService._generate_milestone_insights(user))

        return insights

    @staticmethod
    def _generate_weak_topic_insights(user):
        """Generate insights for weak topics."""
        weak_topics = (
            TopicMastery.objects.filter(
                user=user, mastery_score__lt=50, questions_attempted__gte=3
            )
            .select_related("topic")
            .order_by("mastery_score")[:3]
        )

        insights = []
        expires_at = timezone.now() + timedelta(days=7)

        for mastery in weak_topics:
            insight = Insight.objects.create(
                user=user,
                insight_type="weak_topic",
                insight_data={
                    "topic_id": str(mastery.topic.id),
                    "topic_name": mastery.topic.name,
                    "mastery_score": mastery.mastery_score,
                    "message": f"Focus on {mastery.topic.name} - current mastery {mastery.mastery_score:.1f}%",
                },
                expires_at=expires_at,
            )
            insights.append(insight)

        return insights

    @staticmethod
    def _generate_streak_insights(user):
        """Generate streak-related insights."""
        progress_service = get_progress_service()
        progress = progress_service.get_or_create_progress(user)

        insights = []

        # Check if user hasn't studied today
        today = timezone.now().date()
        today_events = UserEvent.objects.filter(
            user=user, created_at__date=today
        ).exists()

        if not today_events and progress.current_streak > 0:
            insight = Insight.objects.create(
                user=user,
                insight_type="streak_risk",
                insight_data={
                    "current_streak": progress.current_streak,
                    "message": f"Your {progress.current_streak}-day streak is at risk! Study today to keep it alive 🔥",
                },
                expires_at=timezone.now() + timedelta(hours=24),
            )
            insights.append(insight)

        return insights

    @staticmethod
    def _generate_improvement_insights(user):
        """Generate performance improvement insights."""
        # Compare this week vs last week
        from engines.analytics.services.analytics_service import get_analytics_service

        analytics_service = get_analytics_service()

        # This week
        this_week = analytics_service.get_weekly_stats(user)

        # Last week (days 8-14)
        from engines.analytics.models import DailyAggregate

        end_date = timezone.now().date() - timedelta(days=7)
        start_date = end_date - timedelta(days=7)

        last_week_agg = DailyAggregate.objects.filter(
            user=user, date__gte=start_date, date__lte=end_date
        )

        last_week_quizzes = sum(a.quizzes_taken for a in last_week_agg)
        last_week_score = (
            sum(a.total_score for a in last_week_agg) / last_week_quizzes
            if last_week_quizzes > 0
            else 0
        )

        insights = []

        # Check for improvement
        if this_week["average_score"] > last_week_score > 0:
            improvement = this_week["average_score"] - last_week_score

            insight = Insight.objects.create(
                user=user,
                insight_type="improvement",
                insight_data={
                    "improvement": improvement,
                    "current_score": this_week["average_score"],
                    "previous_score": last_week_score,
                    "message": f"Great progress! Your average score improved by {improvement:.1f}% this week 🎉",
                },
                expires_at=timezone.now() + timedelta(days=7),
            )
            insights.append(insight)

        return insights

    @staticmethod
    def _generate_milestone_insights(user):
        """Generate milestone achievement insights."""
        progress_service = get_progress_service()
        progress = progress_service.get_or_create_progress(user)

        insights = []
        milestones = [
            (10, "First 10 quizzes completed!"),
            (25, "25 quizzes milestone reached!"),
            (50, "Half-century! 50 quizzes done!"),
            (100, "Century! 100 quizzes completed! 🏆"),
        ]

        for count, message in milestones:
            if progress.total_quizzes_taken == count:
                insight = Insight.objects.create(
                    user=user,
                    insight_type="milestone",
                    insight_data={"milestone": count, "message": message},
                    expires_at=timezone.now() + timedelta(days=30),
                )
                insights.append(insight)

        return insights

    @staticmethod
    def get_active_insights(user):
        """Get active (non-expired) insights for user."""
        now = timezone.now()

        return (
            Insight.objects.filter(user=user)
            .filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now))
            .order_by("-generated_at")
        )


# Singleton
_insights_service = None


def get_insights_service() -> InsightsService:
    """Get or create global insights service instance."""
    global _insights_service
    if _insights_service is None:
        _insights_service = InsightsService()
    return _insights_service
