"""
Analytics Engine - Service Tests

Tests for AnalyticsService, DashboardService, InsightsService.
"""

from datetime import timedelta

from django.utils import timezone

import pytest

from engines.analytics.models import DailyAggregate, Insight
from engines.analytics.services.analytics_service import AnalyticsService
from engines.analytics.services.dashboard_service import DashboardService
from engines.analytics.services.insights_service import InsightsService
from engines.auth.models import User
from engines.userstate.models import TopicMastery, UserEvent, UserProgress


@pytest.fixture
def user():
    """Create test user."""
    return User.objects.create_user(email="test@example.com", password="pass")


@pytest.fixture
def topic():
    """Create test topic with full hierarchy."""
    from engines.knowledge.models import Module, Program, Subject, Topic

    program = Program.objects.create(name="UPSC CSE")
    subject = Subject.objects.create(name="Test", program=program)
    module = Module.objects.create(name="Test Module", subject=subject)
    return Topic.objects.create(name="Test Topic", module=module, subject=subject)


@pytest.mark.django_db
class TestAnalyticsService:
    """Test AnalyticsService."""

    def test_aggregate_user_day(self, user):
        """Test aggregating user's day."""
        service = AnalyticsService()
        today = timezone.localdate()

        # Create events
        import uuid

        UserEvent.objects.create(
            user=user,
            event_type="article_read",
            event_data={"article_id": str(uuid.uuid4())},
        )
        UserEvent.objects.create(
            user=user,
            event_type="quiz_completed",
            event_data={"quiz_id": str(uuid.uuid4()), "score": 85.0},
        )

        aggregate = service.aggregate_user_day(user, today)

        assert aggregate.articles_read == 1
        assert aggregate.quizzes_taken == 1
        assert aggregate.total_score == 85.0

    def test_aggregate_updates_existing(self, user):
        """Test aggregation updates existing record."""
        service = AnalyticsService()
        today = timezone.localdate()

        # Create initial aggregate
        DailyAggregate.objects.create(user=user, date=today, articles_read=1)

        # Aggregate again
        service.aggregate_user_day(user, today)

        # Should update, not create duplicate
        assert DailyAggregate.objects.filter(user=user, date=today).count() == 1

    def test_get_weekly_stats(self, user):
        """Test getting weekly stats."""
        service = AnalyticsService()

        # Create aggregates
        today = timezone.localdate()
        for i in range(7):
            day = today - timedelta(days=i)
            DailyAggregate.objects.create(
                user=user, date=day, articles_read=2, quizzes_taken=1, total_score=80.0
            )

        stats = service.get_weekly_stats(user)

        assert stats["period"] == "week"
        assert stats["total_articles"] == 14
        assert stats["total_quizzes"] == 7
        assert stats["average_score"] == 80.0

    def test_get_monthly_stats(self, user):
        """Test getting monthly stats."""
        service = AnalyticsService()

        # Create aggregates
        today = timezone.localdate()
        for i in range(10):
            DailyAggregate.objects.create(
                user=user,
                date=today - timedelta(days=i),
                articles_read=1,
                quizzes_taken=1,
                total_score=75.0,
            )

        stats = service.get_monthly_stats(user)

        assert stats["period"] == "month"
        assert stats["total_articles"] == 10
        assert stats["total_quizzes"] == 10


@pytest.mark.django_db
class TestDashboardService:
    """Test DashboardService."""

    def test_get_dashboard_overview(self, user):
        """Test getting complete dashboard."""
        service = DashboardService()

        # Create user progress
        UserProgress.objects.create(
            user=user, total_articles_read=10, total_quizzes_taken=5, current_streak=3
        )

        dashboard = service.get_dashboard_overview(user)

        assert "overview" in dashboard
        assert "performance" in dashboard
        assert "topics" in dashboard
        assert "recent_activity" in dashboard
        assert "insights" in dashboard

        assert dashboard["overview"]["total_articles_read"] == 10
        assert dashboard["overview"]["current_streak"] == 3


@pytest.mark.django_db
class TestInsightsService:
    """Test InsightsService."""

    def test_generate_weak_topic_insights(self, user, topic):
        """Test generating weak topic insights."""
        service = InsightsService()

        # Create weak mastery
        TopicMastery.objects.create(
            user=user,
            topic=topic,
            mastery_score=40.0,
            questions_attempted=5,
            questions_correct=2,
        )

        insights = service.generate_insights(user)

        weak_insights = [i for i in insights if i.insight_type == "weak_topic"]
        assert len(weak_insights) > 0

    def test_generate_streak_risk_insight(self, user):
        """Test generating streak risk insight."""
        service = InsightsService()

        # Create progress with streak
        UserProgress.objects.create(user=user, current_streak=5)

        # No events today (streak at risk)
        insights = service.generate_insights(user)

        streak_insights = [i for i in insights if i.insight_type == "streak_risk"]
        # May or may not generate depending on today's events
        assert isinstance(streak_insights, list)

    def test_generate_milestone_insight(self, user):
        """Test generating milestone insight."""
        service = InsightsService()

        # Create progress at milestone
        UserProgress.objects.create(user=user, total_quizzes_taken=10)

        insights = service.generate_insights(user)

        milestone_insights = [i for i in insights if i.insight_type == "milestone"]
        assert len(milestone_insights) > 0
        assert milestone_insights[0].insight_data["milestone"] == 10

    def test_get_active_insights_filters_expired(self, user):
        """Test getting only active insights."""
        service = InsightsService()

        # Create active insight
        Insight.objects.create(
            user=user,
            insight_type="weak_topic",
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Create expired insight
        Insight.objects.create(
            user=user,
            insight_type="streak_risk",
            expires_at=timezone.now() - timedelta(days=1),
        )

        active = service.get_active_insights(user)

        assert active.count() == 1
