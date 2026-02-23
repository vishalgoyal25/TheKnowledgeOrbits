"""
Article Generation Engine Admin Interface
"""

from typing import Any

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Article, ArticleGenerationJob, ArticleSourceMap


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):  # type: ignore
    """Admin interface for Articles."""

    list_display = [
        "title",
        "topic",
        "generation_type",
        "review_status",
        "is_published",
        "word_count",
        "read_time",
        "quality_score",
        "source_count",
        "created_at",
    ]

    list_filter = [
        "generation_type",
        "review_status",
        "is_published",
        "topic__subject",
        "created_at",
    ]

    search_fields = [
        "title",
        "content",
        "topic__name",
    ]

    readonly_fields = [
        "id",
        "slug",
        "word_count",
        "read_time",
        "quality_score",
        "created_at",
        "updated_at",
        "source_count",
        "static_chunks",
        "ca_chunks",
        "content_preview",
    ]

    fieldsets = [
        (
            "Basic Info",
            {
                "fields": [
                    "id",
                    "title",
                    "slug",
                    "topic",
                    "generation_type",
                ]
            },
        ),
        (
            "Content",
            {
                "fields": [
                    "content",
                    "summary",
                    "content_preview",
                ]
            },
        ),
        (
            "Metadata",
            {
                "fields": [
                    "word_count",
                    "read_time",
                    "quality_score",
                    "generation_metadata",
                ]
            },
        ),
        (
            "Review & Publishing",
            {
                "fields": [
                    "review_status",
                    "is_published",
                    "published_at",
                    "published_by",
                ]
            },
        ),
        (
            "Source Attribution",
            {
                "fields": [
                    "source_count",
                    "static_chunks",
                    "ca_chunks",
                ]
            },
        ),
        (
            "Timestamps",
            {
                "fields": [
                    "created_at",
                    "updated_at",
                ],
                "classes": ["collapse"],
            },
        ),
    ]

    @admin.display(description="Sources")
    def source_count(self, obj) -> Any:  # type: ignore
        """Total chunks used."""
        return obj.source_chunk_count

    @admin.display(description="Static")
    def static_chunks(self, obj) -> Any:  # type: ignore
        """Static chunk count."""
        return obj.static_chunk_count

    @admin.display(description="CA")
    def ca_chunks(self, obj) -> Any:  # type: ignore
        """CA chunk count."""
        return obj.ca_chunk_count

    @admin.display(description="Preview")
    def content_preview(self, obj) -> Any:  # type: ignore
        """First 200 chars of content."""
        if obj.content:
            preview = obj.content[:200]
            return format_html(
                '<div style="max-width:600px;">{}</div>', preview + "..."
            )
        return "-"


@admin.register(ArticleSourceMap)
class ArticleSourceMapAdmin(admin.ModelAdmin):  # type: ignore
    """Admin interface for Article Source Maps."""

    list_display = [
        "article_title",
        "chunk_preview",
        "chunk_source_type",
        "relevance_weight",
        "sequence_order",
        "created_at",
    ]

    list_filter = [
        "chunk__source_type",
        "article__topic__subject",
        "created_at",
    ]

    search_fields = [
        "article__title",
        "chunk__chunk_text",
    ]

    readonly_fields = [
        "id",
        "article",
        "chunk",
        "chunk_preview_full",
        "created_at",
    ]

    fieldsets = [
        (
            "Mapping",
            {
                "fields": [
                    "id",
                    "article",
                    "chunk",
                ]
            },
        ),
        (
            "Metadata",
            {
                "fields": [
                    "relevance_weight",
                    "sequence_order",
                    "chunk_contribution",
                ]
            },
        ),
        (
            "Chunk Details",
            {
                "fields": [
                    "chunk_preview_full",
                ]
            },
        ),
        (
            "Timestamps",
            {
                "fields": [
                    "created_at",
                ],
                "classes": ["collapse"],
            },
        ),
    ]

    @admin.display(description="Article")
    def article_title(self, obj) -> Any:  # type: ignore
        """Article title."""
        return obj.article.title

    @admin.display(description="Chunk")
    def chunk_preview(self, obj) -> Any:  # type: ignore
        """Chunk preview."""
        if obj.chunk:
            return obj.chunk.chunk_text[:80] + "..."
        return "-"

    @admin.display(description="Type")
    def chunk_source_type(self, obj) -> Any:  # type: ignore
        """Chunk source type."""
        if obj.chunk:
            return obj.chunk.source_type.upper()
        return "-"

    @admin.display(description="Full Chunk Text")
    def chunk_preview_full(self, obj) -> Any:  # type: ignore
        """Full chunk text."""
        if obj.chunk:
            return format_html(
                '<div style="max-width:800px; white-space:pre-wrap;">{}</div>',
                obj.chunk.chunk_text,
            )
        return "-"


@admin.register(ArticleGenerationJob)
class ArticleGenerationJobAdmin(admin.ModelAdmin):  # type: ignore
    """Admin interface for Article Generation Jobs."""

    list_display = [
        "topic",
        "status",
        "article_link",
        "requested_by",
        "created_at",
        "completed_at",
        "duration",
    ]

    list_filter = [
        "status",
        "topic__subject",
        "created_at",
    ]

    search_fields = [
        "topic__name",
        "error_log",
    ]

    readonly_fields = [
        "id",
        "topic",
        "article",
        "status",
        "error_log",
        "requested_by",
        "generation_params",
        "started_at",
        "completed_at",
        "created_at",
        "duration",
    ]

    fieldsets = [
        (
            "Job Info",
            {
                "fields": [
                    "id",
                    "topic",
                    "status",
                    "requested_by",
                ]
            },
        ),
        (
            "Result",
            {
                "fields": [
                    "article",
                    "error_log",
                ]
            },
        ),
        (
            "Parameters",
            {
                "fields": [
                    "generation_params",
                ]
            },
        ),
        (
            "Timing",
            {
                "fields": [
                    "created_at",
                    "started_at",
                    "completed_at",
                    "duration",
                ]
            },
        ),
    ]

    @admin.display(description="Article")
    def article_link(self, obj) -> Any:  # type: ignore
        """Link to generated article."""
        if obj.article:
            url = reverse(
                "admin:article_generation_article_change", args=[obj.article.id]
            )
            return format_html('<a href="{}">{}</a>', url, obj.article.title)
        return "-"

    @admin.display(description="Duration")
    def duration(self, obj) -> Any:  # type: ignore
        """Job duration."""
        if obj.started_at and obj.completed_at:
            delta = obj.completed_at - obj.started_at
            return f"{delta.total_seconds():.1f}s"
        return "-"
