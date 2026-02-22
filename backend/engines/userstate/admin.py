"""
User State Engine Admin
"""

from typing import Any

from django.contrib import admin
from engines.userstate.models import (
    UserEvent,
    UserProgress,
    TopicMastery,
    Bookmark,
    ReadingProgress,
)


@admin.register(UserEvent)
class UserEventAdmin(admin.ModelAdmin):  # type: ignore
    """User event admin."""

    list_display = ["user_email", "event_type", "created_at"]
    list_filter = ["event_type", "created_at"]
    search_fields = ["user__email"]
    readonly_fields = ["created_at"]

    @admin.display(description="User")
    def user_email(self, obj) -> Any:  # type: ignore
        return obj.user.email


@admin.register(UserProgress)
class UserProgressAdmin(admin.ModelAdmin):  # type: ignore
    """User progress admin."""

    list_display = [
        "user_email",
        "total_articles_read",
        "total_quizzes_taken",
        "current_streak",
        "syllabus_coverage_percent",
        "updated_at",
    ]
    search_fields = ["user__email"]
    readonly_fields = ["updated_at"]

    @admin.display(description="User")
    def user_email(self, obj) -> Any:  # type: ignore
        return obj.user.email


@admin.register(TopicMastery)
class TopicMasteryAdmin(admin.ModelAdmin):  # type: ignore
    """Topic mastery admin."""

    list_display = [
        "user_email",
        "topic_name",
        "mastery_score",
        "questions_attempted",
        "questions_correct",
        "updated_at",
    ]
    list_filter = ["updated_at"]
    search_fields = ["user__email", "topic__name"]
    readonly_fields = ["updated_at"]

    @admin.display(description="User")
    def user_email(self, obj) -> Any:  # type: ignore
        return obj.user.email

    @admin.display(description="Topic")
    def topic_name(self, obj) -> Any:  # type: ignore
        return obj.topic.name


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):  # type: ignore
    """Bookmark admin."""

    list_display = ["user_email", "content_type", "content_id_short", "created_at"]
    list_filter = ["content_type", "created_at"]
    search_fields = ["user__email"]
    readonly_fields = ["created_at"]

    @admin.display(description="User")
    def user_email(self, obj) -> Any:  # type: ignore
        return obj.user.email

    @admin.display(description="Content ID")
    def content_id_short(self, obj) -> Any:  # type: ignore
        return str(obj.content_id)[:8] + "..."


@admin.register(ReadingProgress)
class ReadingProgressAdmin(admin.ModelAdmin):  # type: ignore
    """Reading progress admin."""

    list_display = [
        "user_email",
        "article_id_short",
        "percent_read",
        "last_position",
        "updated_at",
    ]
    search_fields = ["user__email"]
    readonly_fields = ["updated_at"]

    @admin.display(description="User")
    def user_email(self, obj) -> Any:  # type: ignore
        return obj.user.email

    @admin.display(description="Article")
    def article_id_short(self, obj) -> Any:  # type: ignore
        return str(obj.article_id)[:8] + "..."
