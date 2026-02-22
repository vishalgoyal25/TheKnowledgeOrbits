"""
Analytics Engine - Model Tests

Tests for DailyAggregate and Insight models.
"""

import pytest
import uuid
from datetime import date, timedelta
from django.utils import timezone
from engines.analytics.models import DailyAggregate, Insight
from engines.auth.models import User


@pytest.fixture
def user():
    """Create test user."""
    return User.objects.create_user(email="test@example.com", password="pass")


@pytest.mark.django_db
class TestDailyAggregateModel:
    """Test DailyAggregate model."""

    def test_create_aggregate(self, user):
        """Test creating daily aggregate."""
        today = date.today()

        aggregate = DailyAggregate.objects.create(
            user=user,
            date=today,
            articles_read=5,
            quizzes_taken=3,
            total_score=240.0,
            time_spent_seconds=3600,
        )

        assert aggregate.user == user
        assert aggregate.date == today
        assert aggregate.articles_read == 5
        assert aggregate.quizzes_taken == 3

    def test_aggregate_has_uuid(self, user):
        """Test aggregate has UUID primary key."""
        aggregate = DailyAggregate.objects.create(user=user, date=date.today())

        assert isinstance(aggregate.id, uuid.UUID)
        assert len(str(aggregate.id)) == 36

    def test_unique_user_date_constraint(self, user):
        """Test user can't have duplicate aggregates for same date."""
        today = date.today()

        DailyAggregate.objects.create(user=user, date=today)

        with pytest.raises(Exception):  # IntegrityError
            DailyAggregate.objects.create(user=user, date=today)

    def test_average_score_property(self, user):
        """Test average_score calculation."""
        aggregate = DailyAggregate.objects.create(
            user=user, date=date.today(), quizzes_taken=4, total_score=320.0
        )

        assert aggregate.average_score == 80.0

    def test_average_score_with_no_quizzes(self, user):
        """Test average_score returns 0 when no quizzes."""
        aggregate = DailyAggregate.objects.create(
            user=user, date=date.today(), quizzes_taken=0, total_score=0.0
        )

        assert aggregate.average_score == 0.0

    def test_aggregate_ordering(self, user):
        """Test aggregates ordered by date descending."""
        today = date.today()
        yesterday = today - timedelta(days=1)

        agg1 = DailyAggregate.objects.create(user=user, date=yesterday)
        agg2 = DailyAggregate.objects.create(user=user, date=today)

        aggregates = list(DailyAggregate.objects.all())
        assert aggregates[0] == agg2
        assert aggregates[1] == agg1

    def test_aggregate_defaults(self, user):
        """Test aggregate fields default to zero."""
        aggregate = DailyAggregate.objects.create(user=user, date=date.today())

        assert aggregate.articles_read == 0
        assert aggregate.quizzes_taken == 0
        assert aggregate.total_score == 0.0
        assert aggregate.time_spent_seconds == 0


@pytest.mark.django_db
class TestInsightModel:
    """Test Insight model."""

    def test_create_insight(self, user):
        """Test creating insight."""
        insight = Insight.objects.create(
            user=user,
            insight_type="weak_topic",
            insight_data={"topic": "Polity", "score": 45.0},
            expires_at=timezone.now() + timedelta(days=7),
        )

        assert insight.user == user
        assert insight.insight_type == "weak_topic"
        assert "topic" in insight.insight_data

    def test_insight_has_uuid(self, user):
        """Test insight has UUID primary key."""
        insight = Insight.objects.create(user=user, insight_type="milestone")

        assert isinstance(insight.id, uuid.UUID)

    def test_is_expired_property(self, user):
        """Test is_expired property."""
        # Non-expired insight
        future = timezone.now() + timedelta(days=1)
        insight1 = Insight.objects.create(
            user=user, insight_type="weak_topic", expires_at=future
        )

        assert not insight1.is_expired

        # Expired insight
        past = timezone.now() - timedelta(days=1)
        insight2 = Insight.objects.create(
            user=user, insight_type="streak_risk", expires_at=past
        )

        assert insight2.is_expired

    def test_insight_without_expiry(self, user):
        """Test insight without expiry never expires."""
        insight = Insight.objects.create(
            user=user, insight_type="milestone", expires_at=None
        )

        assert not insight.is_expired

    def test_insight_ordering(self, user):
        """Test insights ordered by generated_at descending."""
        i1 = Insight.objects.create(user=user, insight_type="weak_topic")
        i2 = Insight.objects.create(user=user, insight_type="milestone")

        insights = list(Insight.objects.all())
        assert insights[0] == i2
        assert insights[1] == i1

    def test_insight_str_representation(self, user):
        """Test insight string representation."""
        insight = Insight.objects.create(user=user, insight_type="weak_topic")

        assert user.email in str(insight)
        assert "Weak Topic" in str(insight)
