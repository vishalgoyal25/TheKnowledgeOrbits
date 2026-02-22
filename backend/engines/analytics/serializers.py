"""
Analytics Engine Serializers
"""

from rest_framework import serializers
from engines.analytics.models import DailyAggregate, Insight


class DailyAggregateSerializer(serializers.ModelSerializer):
    """Daily aggregate serializer."""

    average_score = serializers.FloatField(read_only=True)

    class Meta:
        model = DailyAggregate
        fields = [
            "id",
            "date",
            "articles_read",
            "quizzes_taken",
            "total_score",
            "average_score",
            "time_spent_seconds",
            "created_at",
        ]
        read_only_fields = fields


class InsightSerializer(serializers.ModelSerializer):
    """Insight serializer."""

    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = Insight
        fields = [
            "id",
            "insight_type",
            "insight_data",
            "generated_at",
            "expires_at",
            "is_expired",
        ]
        read_only_fields = fields
