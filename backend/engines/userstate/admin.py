"""
User State Engine Admin
"""

from django.contrib import admin
from engines.userstate.models import (
    UserEvent,
    UserProgress,
    TopicMastery,
    Bookmark,
    ReadingProgress,
)


@admin.register(UserEvent)
class UserEventAdmin(admin.ModelAdmin):
    """User event admin."""

    list_display = ["user_email", "event_type", "created_at"]
    list_filter = ["event_type", "created_at"]
    search_fields = ["user__email"]
    readonly_fields = ["created_at"]

    def user_email(self, obj):
        return obj.user.email

    user_email.short_description = "User"


@admin.register(UserProgress)
class UserProgressAdmin(admin.ModelAdmin):
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

    def user_email(self, obj):
        return obj.user.email

    user_email.short_description = "User"


@admin.register(TopicMastery)
class TopicMasteryAdmin(admin.ModelAdmin):
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

    def user_email(self, obj):
        return obj.user.email

    user_email.short_description = "User"

    def topic_name(self, obj):
        return obj.topic.name

    topic_name.short_description = "Topic"


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    """Bookmark admin."""

    list_display = ["user_email", "content_type", "content_id_short", "created_at"]
    list_filter = ["content_type", "created_at"]
    search_fields = ["user__email"]
    readonly_fields = ["created_at"]

    def user_email(self, obj):
        return obj.user.email

    user_email.short_description = "User"

    def content_id_short(self, obj):
        return str(obj.content_id)[:8] + "..."

    content_id_short.short_description = "Content ID"


@admin.register(ReadingProgress)
class ReadingProgressAdmin(admin.ModelAdmin):
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

    def user_email(self, obj):
        return obj.user.email

    user_email.short_description = "User"

    def article_id_short(self, obj):
        return str(obj.article_id)[:8] + "..."

    article_id_short.short_description = "Article"
