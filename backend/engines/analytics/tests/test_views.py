"""
Analytics Engine - View Tests

Tests for all 5 API endpoints.
"""

import pytest
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status
from django.core.cache import cache
from django.utils import timezone
from engines.auth.models import User
from engines.analytics.models import DailyAggregate, Insight
from engines.userstate.models import UserEvent


@pytest.fixture
def api_client():
    """API client fixture."""
    return APIClient()


@pytest.fixture
def user():
    """Create test user."""
    user = User.objects.create_user(email="test@example.com", password="pass")
    user.is_verified = True
    user.save()
    return user


@pytest.fixture
def authenticated_client(api_client, user):
    """Authenticated API client."""
    api_client.force_authenticate(user=user)
    return api_client, user


@pytest.mark.django_db
class TestGetDashboardView:
    """Test get dashboard endpoint."""

    def test_get_dashboard_success(self, authenticated_client):
        """Test getting dashboard data."""
        client, user = authenticated_client

        # Create some data
        UserEvent.objects.create(user=user, event_type="article_read")

        response = client.get("/api/v1/analytics/dashboard/")

        assert response.status_code == status.HTTP_200_OK
        assert "overview" in response.data
        assert "performance" in response.data
        assert "topics" in response.data
        assert "insights" in response.data

    def test_dashboard_caching(self, authenticated_client):
        """Test dashboard data is cached."""
        client, user = authenticated_client

        # First request
        response1 = client.get("/api/v1/analytics/dashboard/")

        # Second request (should hit cache)
        response2 = client.get("/api/v1/analytics/dashboard/")

        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK

    def test_dashboard_unauthenticated(self, api_client):
        """Test dashboard requires authentication."""
        response = api_client.get("/api/v1/analytics/dashboard/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestGetWeeklyStatsView:
    """Test get weekly stats endpoint."""

    def test_get_weekly_stats(self, authenticated_client):
        """Test getting weekly statistics."""
        client, user = authenticated_client

        # Create aggregates for last 7 days
        today = timezone.localdate()
        for i in range(7):
            day = today - timedelta(days=i)
            DailyAggregate.objects.create(
                user=user, date=day, articles_read=2, quizzes_taken=1, total_score=80.0
            )

        response = client.get("/api/v1/analytics/weekly-stats/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["period"] == "week"
        assert "daily_data" in response.data
        assert response.data["total_articles"] == 14
        assert response.data["total_quizzes"] == 7


@pytest.mark.django_db
class TestGetMonthlyStatsView:
    """Test get monthly stats endpoint."""

    def test_get_monthly_stats(self, authenticated_client):
        """Test getting monthly statistics."""
        client, user = authenticated_client

        # Create some aggregates
        today = timezone.now().date()
        for i in range(10):
            day = today - timedelta(days=i)
            DailyAggregate.objects.create(
                user=user, date=day, articles_read=1, quizzes_taken=1, total_score=75.0
            )

        response = client.get("/api/v1/analytics/monthly-stats/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["period"] == "month"
        assert "daily_data" in response.data


@pytest.mark.django_db
class TestGetInsightsView:
    """Test get insights endpoint."""

    def test_get_active_insights(self, authenticated_client):
        """Test getting active insights."""
        client, user = authenticated_client
        from django.utils import timezone

        # Create insights
        Insight.objects.create(
            user=user,
            insight_type="weak_topic",
            expires_at=timezone.now() + timedelta(days=7),
        )
        Insight.objects.create(user=user, insight_type="milestone", expires_at=None)

        response = client.get("/api/v1/analytics/insights/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_expired_insights_not_returned(self, authenticated_client):
        """Test expired insights are filtered out."""
        client, user = authenticated_client
        from django.utils import timezone

        # Create expired insight
        Insight.objects.create(
            user=user,
            insight_type="streak_risk",
            expires_at=timezone.now() - timedelta(days=1),
        )

        response = client.get("/api/v1/analytics/insights/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0


@pytest.mark.django_db
class TestGenerateInsightsView:
    """Test generate insights endpoint."""

    def test_generate_insights(self, authenticated_client):
        """Test generating new insights."""
        client, user = authenticated_client

        response = client.post("/api/v1/analytics/generate-insights/")

        assert response.status_code == status.HTTP_201_CREATED
        assert isinstance(response.data, list)

    def test_generate_insights_invalidates_cache(self, authenticated_client):
        """Test generating insights clears dashboard cache."""
        client, user = authenticated_client

        # Set cache
        cache_key = f"dashboard_{user.id}"
        cache.set(cache_key, {"test": "data"}, 300)

        # Generate insights
        client.post("/api/v1/analytics/generate-insights/")

        # Check cache cleared
        cached = cache.get(cache_key)
        assert cached is None
