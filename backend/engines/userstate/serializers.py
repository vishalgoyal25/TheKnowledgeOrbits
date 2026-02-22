"""
User State Engine Serializers
"""

from rest_framework import serializers
from engines.userstate.models import (
    UserEvent,
    UserProgress,
    TopicMastery,
    Bookmark,
    ReadingProgress,
)


class UserEventSerializer(serializers.ModelSerializer):
    """User event serializer."""

    class Meta:
        model = UserEvent
        fields = ["id", "event_type", "event_data", "created_at"]
        read_only_fields = ["id", "created_at"]


class UserProgressSerializer(serializers.ModelSerializer):
    """User progress serializer."""

    class Meta:
        model = UserProgress
        fields = [
            "total_articles_read",
            "total_quizzes_taken",
            "current_streak",
            "syllabus_coverage_percent",
            "updated_at",
        ]
        read_only_fields = fields


class TopicMasterySerializer(serializers.ModelSerializer):
    """Topic mastery serializer."""

    topic_name = serializers.CharField(source="topic.name", read_only=True)

    class Meta:
        model = TopicMastery
        fields = [
            "id",
            "topic",
            "topic_name",
            "mastery_score",
            "questions_attempted",
            "questions_correct",
            "updated_at",
        ]
        read_only_fields = ["id", "mastery_score", "updated_at"]


class BookmarkSerializer(serializers.ModelSerializer):
    """Bookmark serializer."""

    class Meta:
        model = Bookmark
        fields = ["id", "content_type", "content_id", "notes", "created_at"]
        read_only_fields = ["id", "created_at"]


class BookmarkCreateSerializer(serializers.Serializer):
    """Bookmark creation serializer."""

    content_type = serializers.ChoiceField(
        choices=["article", "quiz", "chunk"], required=True
    )
    content_id = serializers.UUIDField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class ReadingProgressSerializer(serializers.ModelSerializer):
    """Reading progress serializer."""

    article_title = serializers.SerializerMethodField()
    topic_name = serializers.SerializerMethodField()

    class Meta:
        model = ReadingProgress
        fields = [
            "id",
            "article_id",
            "article_title",
            "topic_name",
            "percent_read",
            "last_position",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]

    def get_article_title(self, obj):
        try:
            from engines.content.models import Article

            return Article.objects.get(id=obj.article_id).title
        except Exception:
            return "Unknown Article"

    def get_topic_name(self, obj):
        try:
            from engines.content.models import Article

            return Article.objects.get(id=obj.article_id).topic.name
        except Exception:
            return "Unknown Topic"


class ReadingProgressUpdateSerializer(serializers.Serializer):
    """Reading progress update serializer."""

    article_id = serializers.UUIDField(required=True)
    percent_read = serializers.FloatField(required=True, min_value=0, max_value=100)
    last_position = serializers.IntegerField(required=True, min_value=0)
