from django.contrib import admin
from .models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "user_type", "institution", "created_at")
    list_filter = ("user_type", "created_at")
    search_fields = ("name", "email", "message", "institution")
    readonly_fields = ("created_at",)
