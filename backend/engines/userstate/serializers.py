from typing import Any

import sentry_sdk

"""
User State Engine Serializers
"""

from rest_framework import serializers

from engines.userstate.models import (
    Bookmark,
    ReadingProgress,
    TopicMastery,
    UserEvent,
    UserProgress,
)


class UserEventSerializer(serializers.ModelSerializer):  # type: ignore
    """User event serializer."""

    class Meta:
        model = UserEvent
        fields = ["id", "event_type", "event_data", "created_at"]
        read_only_fields = ["id", "created_at"]


class UserProgressSerializer(serializers.ModelSerializer):  # type: ignore
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


class TopicMasterySerializer(serializers.ModelSerializer):  # type: ignore
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


class BookmarkSerializer(serializers.ModelSerializer):  # type: ignore
    """Bookmark serializer with expanded content details."""

    content = serializers.SerializerMethodField()

    class Meta:
        model = Bookmark
        fields = ["id", "content_type", "content_id", "notes", "created_at", "content"]
        read_only_fields = ["id", "created_at"]

    def get_content(self, obj: Any) -> Any:
        """Fetch title and topic from the bookmarked Article or Quiz."""
        try:
            if obj.content_type == "article":
                from engines.article_generation.models import Article

                article = Article.objects.select_related("topic").get(id=obj.content_id)
                return {
                    "id": str(article.id),
                    "title": article.title,
                    "topic": {
                        "id": str(article.topic.id),
                        "name": article.topic.name,
                    },
                }
            elif obj.content_type == "quiz":
                from engines.assessment.models import Quiz

                quiz = Quiz.objects.select_related("topic").get(id=obj.content_id)
                return {
                    "id": str(quiz.id),
                    "title": quiz.title,
                    "topic": {
                        "id": str(quiz.topic.id),
                        "name": quiz.topic.name,
                    },
                    "difficulty_level": quiz.difficulty_level,
                    "question_count": quiz.question_count,
                }
        except Exception:
            pass
        return None


class BookmarkCreateSerializer(serializers.Serializer):  # type: ignore
    """Bookmark creation serializer."""

    content_type = serializers.ChoiceField(
        choices=["article", "quiz", "chunk"], required=True
    )
    content_id = serializers.UUIDField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class ReadingProgressSerializer(serializers.ModelSerializer):  # type: ignore
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

    def get_article_title(self, obj) -> Any:  # type: ignore
        try:
            from engines.content.models import Article  # type: ignore

            return Article.objects.get(id=obj.article_id).title
        except Exception:
            sentry_sdk.capture_message("Handled Exception without var")
            return "Unknown Article"

    def get_topic_name(self, obj) -> Any:  # type: ignore
        try:
            from engines.content.models import Article  # type: ignore

            return Article.objects.get(id=obj.article_id).topic.name
        except Exception:
            sentry_sdk.capture_message("Handled Exception without var")
            return "Unknown Topic"


class ReadingProgressUpdateSerializer(serializers.Serializer):  # type: ignore
    """Reading progress update serializer."""

    article_id = serializers.UUIDField(required=True)
    percent_read = serializers.FloatField(required=True, min_value=0, max_value=100)
    last_position = serializers.IntegerField(required=True, min_value=0)
