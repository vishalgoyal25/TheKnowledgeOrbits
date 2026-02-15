"""
Auth Engine Admin Interface
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from engines.auth.models import User, Role, RoleAssignment


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom user admin."""
    
    list_display = ['email', 'full_name', 'is_verified_badge', 'subscription_tier', 'created_at']
    list_filter = ['is_verified', 'subscription_tier', 'is_staff', 'created_at']
    search_fields = ['email', 'full_name']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Account', {
            'fields': ('email', 'password', 'full_name')
        }),
        ('Status', {
            'fields': ('is_verified', 'subscription_tier')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser')
        }),
        ('Verification', {
            'fields': ('verification_token', 'verification_sent_at'),
            'classes': ('collapse',)
        }),
        ('Reset', {
            'fields': ('reset_token', 'reset_sent_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_login'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'last_login']
    
    def is_verified_badge(self, obj):
        if obj.is_verified:
            return format_html('<span style="color: green;">✓ Verified</span>')
        return format_html('<span style="color: red;">✗ Not Verified</span>')
    is_verified_badge.short_description = 'Status'


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Role admin."""
    
    list_display = ['name', 'description', 'user_count', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at']
    
    def user_count(self, obj):
        return obj.assignments.count()
    user_count.short_description = 'Users'


@admin.register(RoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):
    """Role assignment admin."""
    
    list_display = ['user_email', 'role_name', 'created_at']
    list_filter = ['role', 'created_at']
    search_fields = ['user__email']
    readonly_fields = ['created_at']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    def role_name(self, obj):
        return obj.role.get_name_display()
    role_name.short_description = 'Role'
    