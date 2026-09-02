"""
Telemetry Engine Admin

This IS the G1 dashboard. Deliberately so: Django admin gives a filterable view
of both tables for roughly zero build cost, and building a custom analytics UI
for traffic that does not exist yet would be premature. Revisit when row volume
justifies it.

Both models are READ-ONLY here. Telemetry is written by machines — the request
middleware and the read beacon — and a hand-edited row is a corrupted record
with no way to tell it apart from a real one. Lifecycle is handled by the
retention prune, not by anyone clicking delete.
"""

from typing import Any

from django.contrib import admin

from engines.telemetry.models import ContentRead, VisitLog


class ReadOnlyTelemetryAdmin(admin.ModelAdmin):  # type: ignore
    """
    Shared base: look, don't touch.

    `show_full_result_count = False` matters more than it looks. By default the
    admin runs an unfiltered COUNT(*) on every list page to render "1234 total".
    On a telemetry table that grows all day, against Supabase from a 512 MB
    dyno, that is a full scan on every page view. Turning it off shows
    "Show all" instead and costs nothing.
    """

    show_full_result_count = False
    list_per_page = 50

    def has_add_permission(self, request: Any) -> bool:
        return False

    def has_change_permission(self, request: Any, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: Any, obj: Any = None) -> bool:
        return False


@admin.register(VisitLog)
class VisitLogAdmin(ReadOnlyTelemetryAdmin):
    """Server-visible requests. NOT page views — see the model docstring."""

    list_display = [
        "created_at",
        "method",
        "path",
        "status_code",
        "is_authenticated",
        "visitor",
    ]
    list_filter = ["status_code", "is_authenticated", "method", "created_at"]
    search_fields = ["path"]
    search_help_text = (
        "Substring match on path. This cannot use an index — avoid on large ranges."
    )

    @admin.display(description="Visitor")
    def visitor(self, obj: Any) -> str:
        """
        First 8 characters of the salted hash.

        Enough to eyeball whether several rows came from one visitor; useless
        for identifying anyone, which is the whole point. The full 64-character
        digest adds nothing to a human reading a list.
        """
        return obj.ip_hash[:8]


@admin.register(ContentRead)
class ContentReadAdmin(ReadOnlyTelemetryAdmin):
    """Actual readership — one row per reader, per item, per day."""

    list_display = [
        "read_date",
        "content_type",
        "content_id",
        "is_authenticated",
        "visitor",
        "created_at",
    ]
    list_filter = ["content_type", "is_authenticated", "read_date"]
    search_fields = ["content_id"]
    search_help_text = "Substring match on slug or id."

    @admin.display(description="Visitor")
    def visitor(self, obj: Any) -> str:
        """First 8 characters of the salted hash — see VisitLogAdmin.visitor."""
        return obj.ip_hash[:8]
