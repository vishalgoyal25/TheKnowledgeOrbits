"""
engines/tags/admin.py
━━━━━━━━━━━━━━━━━━━━━
Phase L — Tags Engine Django Admin registration.
"""

from django.contrib import admin

from engines.tags.models import ArticleTag, ConceptArticleLink, ConceptPage, Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "tag_type", "usage_count", "is_active", "created_at"]
    list_filter = ["tag_type", "is_active"]
    search_fields = ["name", "slug"]
    readonly_fields = ["id", "slug", "usage_count", "created_at", "updated_at"]
    ordering = ["-usage_count", "name"]


@admin.register(ArticleTag)
class ArticleTagAdmin(admin.ModelAdmin):
    list_display = ["tag", "content_type", "object_id", "relevance", "created_at"]
    list_filter = ["content_type"]
    search_fields = ["tag__name"]
    readonly_fields = ["id", "created_at"]


@admin.register(ConceptPage)
class ConceptPageAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_content_ready", "usage_count", "created_at"]
    list_filter = ["is_content_ready"]
    search_fields = ["name", "slug"]
    readonly_fields = ["id", "usage_count", "created_at", "updated_at"]
    ordering = ["-usage_count", "name"]


@admin.register(ConceptArticleLink)
class ConceptArticleLinkAdmin(admin.ModelAdmin):
    list_display = ["concept_page", "daily_ca_article_id", "created_at"]
    search_fields = ["concept_page__name"]
    readonly_fields = ["id", "created_at"]
