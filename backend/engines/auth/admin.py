"""
Auth Engine Admin Interface
"""

from typing import Any

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from engines.auth.models import User, Role, RoleAssignment


@admin.register(User)
class UserAdmin(BaseUserAdmin):  # type: ignore
    """Custom user admin."""

    list_display = [
        "email",
        "full_name",
        "is_verified_badge",
        "subscription_tier",
        "created_at",
    ]
    list_filter = ["is_verified", "subscription_tier", "is_staff", "created_at"]
    search_fields = ["email", "full_name"]
    ordering = ["-created_at"]

    fieldsets = (
        ("Account", {"fields": ("email", "password", "full_name")}),
        ("Status", {"fields": ("is_verified", "subscription_tier")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),
        (
            "Verification",
            {
                "fields": ("verification_token", "verification_sent_at"),
                "classes": ("collapse",),
            },
        ),
        (
            "Reset",
            {"fields": ("reset_token", "reset_sent_at"), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at", "last_login"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ["created_at", "updated_at", "last_login"]

    @admin.display(description="Status")
    def is_verified_badge(self, obj) -> Any:  # type: ignore
        if obj.is_verified:
            return format_html('<span style="color: green;">✓ Verified</span>')
        return format_html('<span style="color: red;">✗ Not Verified</span>')


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):  # type: ignore
    """Role admin."""

    list_display = ["name", "description", "user_count", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at"]

    @admin.display(description="Users")
    def user_count(self, obj) -> Any:  # type: ignore
        return obj.assignments.count()


@admin.register(RoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):  # type: ignore
    """Role assignment admin."""

    list_display = ["user_email", "role_name", "created_at"]
    list_filter = ["role", "created_at"]
    search_fields = ["user__email"]
    readonly_fields = ["created_at"]

    @admin.display(description="User")
    def user_email(self, obj) -> Any:  # type: ignore
        return obj.user.email

    @admin.display(description="Role")
    def role_name(self, obj) -> Any:  # type: ignore
        return obj.role.get_name_display()
