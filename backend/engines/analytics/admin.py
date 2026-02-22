"""
Analytics Engine Admin
"""

from django.contrib import admin
from engines.analytics.models import DailyAggregate, Insight


@admin.register(DailyAggregate)
class DailyAggregateAdmin(admin.ModelAdmin):
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

    def user_email(self, obj):
        return obj.user.email

    user_email.short_description = "User"

    def average_score_display(self, obj):
        return f"{obj.average_score:.1f}%"

    average_score_display.short_description = "Avg Score"


@admin.register(Insight)
class InsightAdmin(admin.ModelAdmin):
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

    def user_email(self, obj):
        return obj.user.email

    user_email.short_description = "User"

    def is_expired_display(self, obj):
        if obj.is_expired:
            return "✗ Expired"
        return "✓ Active"

    is_expired_display.short_description = "Status"
