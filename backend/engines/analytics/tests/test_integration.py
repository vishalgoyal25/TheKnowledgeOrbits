"""
Analytics Engine - Integration Tests

End-to-end analytics workflow tests.
"""

from datetime import timedelta

from django.utils import timezone

from rest_framework import status
from rest_framework.test import APIClient

import pytest

from engines.analytics.models import DailyAggregate
from engines.analytics.services.analytics_service import AnalyticsService
from engines.auth.models import User
from engines.userstate.models import TopicMastery, UserProgress


@pytest.fixture
def api_client():
    """API client."""
    return APIClient()


@pytest.fixture
def authenticated_user(api_client):
    """Authenticated user and client."""
    user = User.objects.create_user(email="test@example.com", password="pass")
    user.is_verified = True
    user.save()
    api_client.force_authenticate(user=user)
    return api_client, user


@pytest.mark.django_db
class TestAnalyticsAggregationFlow:
    """Test complete analytics aggregation workflow."""

    def test_events_to_aggregation_to_dashboard(self, authenticated_user):
        """Test: Events → Aggregation → Dashboard display."""
        client, user = authenticated_user
        from engines.userstate.services.activity_service import ActivityService

        # Step 1: Create user events
        activity = ActivityService()
        import uuid

        activity.log_article_read(user, str(uuid.uuid4()))
        activity.log_quiz_completed(user, str(uuid.uuid4()), str(uuid.uuid4()), 85.0)

        # Step 2: Aggregate today's data
        analytics = AnalyticsService()
        today = timezone.localdate()
        aggregate = analytics.aggregate_user_day(user, today)

        assert aggregate.articles_read == 1
        assert aggregate.quizzes_taken == 1

        # Step 3: View in dashboard
        response = client.get("/api/v1/analytics/dashboard/")

        assert response.status_code == status.HTTP_200_OK
        assert "overview" in response.data


@pytest.mark.django_db
class TestInsightsGenerationFlow:
    """Test insights generation workflow."""

    def test_weak_topic_insight_generation(self, authenticated_user):
        """Test generating insights for weak topics."""
        client, user = authenticated_user
        from engines.knowledge.models import Module, Program, Subject, Topic

        # Step 1: Create weak mastery
        program = Program.objects.create(name="UPSC CSE")
        subject = Subject.objects.create(name="Test", program=program)
        module = Module.objects.create(name="Test Module", subject=subject)
        topic = Topic.objects.create(name="Weak Topic", module=module, subject=subject)
        TopicMastery.objects.create(
            user=user,
            topic=topic,
            mastery_score=30.0,
            questions_attempted=5,
            questions_correct=1,
        )

        # Step 2: Generate insights
        response = client.post("/api/v1/analytics/generate-insights/")

        assert response.status_code == status.HTTP_201_CREATED

        # Step 3: View insights
        response = client.get("/api/v1/analytics/insights/")

        assert len(response.data) > 0
        weak_insights = [i for i in response.data if i["insight_type"] == "weak_topic"]
        assert len(weak_insights) > 0


@pytest.mark.django_db
class TestWeeklyPerformanceTracking:
    """Test weekly performance tracking."""

    def test_track_performance_over_week(self, authenticated_user):
        """Test tracking performance trends over a week."""
        client, user = authenticated_user

        # Create data for 7 days
        today = timezone.localdate()
        for i in range(7):
            day = today - timedelta(days=i)
            DailyAggregate.objects.create(
                user=user,
                date=day,
                articles_read=2,
                quizzes_taken=1,
                total_score=75.0 + i * 2,  # Improving scores
            )

        # Get weekly stats
        response = client.get("/api/v1/analytics/weekly-stats/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["daily_data"]) == 7
        assert response.data["total_quizzes"] == 7


@pytest.mark.django_db
class TestProgressAndAnalyticsCombined:
    """Test progress and analytics working together."""

    def test_progress_feeds_into_analytics(self, authenticated_user):
        """Test user progress data appears in analytics."""
        client, user = authenticated_user

        # Create progress
        UserProgress.objects.create(
            user=user,
            total_articles_read=15,
            total_quizzes_taken=10,
            current_streak=7,
            syllabus_coverage_percent=45.5,
        )

        # View dashboard
        response = client.get("/api/v1/analytics/dashboard/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["overview"]["total_articles_read"] == 15
        assert response.data["overview"]["current_streak"] == 7
        assert response.data["overview"]["syllabus_coverage"] == 45.5
