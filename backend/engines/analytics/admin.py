"""
Analytics Engine Admin
"""

from typing import Any

from django.contrib import admin
from engines.analytics.models import DailyAggregate, Insight


@admin.register(DailyAggregate)
class DailyAggregateAdmin(admin.ModelAdmin):  # type: ignore
    """Daily aggregate admin."""

    list_display = [
        "user_email",
        "date",
        "articles_read",
        "quizzes_taken",
        "average_score_display",
        "created_at",
    ]
    list_filter = ["date", "created_at"]
    search_fields = ["user__email"]
    readonly_fields = ["created_at"]
    date_hierarchy = "date"

    @admin.display(description="User")
    def user_email(self, obj) -> Any:  # type: ignore
        return obj.user.email

    @admin.display(description="Avg Score")
    def average_score_display(self, obj) -> Any:  # type: ignore
        return f"{obj.average_score:.1f}%"


@admin.register(Insight)
class InsightAdmin(admin.ModelAdmin):  # type: ignore
    """Insight admin."""

    list_display = [
        "user_email",
        "insight_type",
        "is_expired_display",
        "generated_at",
        "expires_at",
    ]
    list_filter = ["insight_type", "generated_at"]
    search_fields = ["user__email"]
    readonly_fields = ["generated_at"]

    @admin.display(description="User")
    def user_email(self, obj) -> Any:  # type: ignore
        return obj.user.email

    @admin.display(description="Status")
    def is_expired_display(self, obj) -> Any:  # type: ignore
        if obj.is_expired:
            return "✗ Expired"
        return "✓ Active"
