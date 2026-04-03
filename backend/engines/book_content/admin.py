"""
Book Content Engine — Admin Interface
Registers all 6 models for Django admin monitoring and manual inspection.
Useful for: verifying generation output, checking quality scores, audit logs.
"""

from typing import Any

from django.contrib import admin
from django.utils.html import format_html

from engines.book_content.models import (
    BookContent,
    BookPlan,
    ContentMedia,
    CrossReference,
    GenerationLog,
    TopicRelation,
)


# ─────────────────────────────────────────────────────────────────────────────
# BOOK PLAN
# ─────────────────────────────────────────────────────────────────────────────


@admin.register(BookPlan)
class BookPlanAdmin(admin.ModelAdmin):  # type: ignore
    """Admin interface for BookPlan — one plan per subject."""

    list_display = [
        "subject",
        "generation_status",
        "topics_planned",
        "topics_completed",
        "completion_pct",
        "avg_quality_score",
        "created_at",
    ]
    list_filter = ["generation_status", "created_at"]
    search_fields = ["subject__name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

    fieldsets = (
        (
            "Subject",
            {"fields": ("id", "subject", "generation_status")},
        ),
        (
            "Progress",
            {"fields": ("topics_planned", "topics_completed", "avg_quality_score")},
        ),
        (
            "Intelligence Data",
            {
                "fields": (
                    "toc_json",
                    "reading_order",
                    "prerequisite_chains",
                    "concept_registry",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="Completion %")
    def completion_pct(self, obj: BookPlan) -> str:
        if not obj.topics_planned:
            return "—"
        pct = (obj.topics_completed / obj.topics_planned) * 100
        return f"{pct:.1f}%"


# ─────────────────────────────────────────────────────────────────────────────
# BOOK CONTENT
# ─────────────────────────────────────────────────────────────────────────────


@admin.register(BookContent)
class BookContentAdmin(admin.ModelAdmin):  # type: ignore
    """Admin interface for BookContent — one article per topic node."""

    list_display = [
        "topic",
        "subject",
        "quality_score",
        "word_count",
        "generation_pass",
        "source_mode",
        "has_tables",
        "is_published",
        "created_at",
    ]
    list_filter = [
        "subject",
        "source_mode",
        "is_published",
        "has_tables",
        "has_media",
        "created_at",
    ]
    search_fields = ["topic__name", "subject__name"]
    readonly_fields = [
        "id",
        "word_count",
        "content_preview",
        "created_at",
        "updated_at",
    ]
    ordering = ["-quality_score", "-created_at"]

    fieldsets = (
        (
            "Topic",
            {"fields": ("id", "topic", "subject")},
        ),
        (
            "Quality",
            {
                "fields": (
                    "quality_score",
                    "word_count",
                    "generation_pass",
                    "source_mode",
                )
            },
        ),
        (
            "Flags",
            {"fields": ("has_tables", "has_media", "is_published")},
        ),
        (
            "Content Preview",
            {"fields": ("content_preview",), "classes": ("collapse",)},
        ),
        (
            "Full Content",
            {
                "fields": ("content_markdown", "formatted_content"),
                "classes": ("collapse",),
            },
        ),
        (
            "Critique Log",
            {"fields": ("critique_log",), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="Content Preview")
    def content_preview(self, obj: BookContent) -> Any:
        """Show first 300 chars of article for quick review."""
        if not obj.content_markdown:
            return "—"
        preview = obj.content_markdown[:300]
        return format_html("<pre style='white-space:pre-wrap'>{}</pre>", preview)


# ─────────────────────────────────────────────────────────────────────────────
# TOPIC RELATION
# ─────────────────────────────────────────────────────────────────────────────


@admin.register(TopicRelation)
class TopicRelationAdmin(admin.ModelAdmin):  # type: ignore
    """Admin interface for TopicRelation — semantic graph edges."""

    list_display = [
        "source_topic",
        "relation_type",
        "target_topic",
        "similarity_score",
        "is_auto_detected",
        "created_at",
    ]
    list_filter = ["relation_type", "is_auto_detected", "created_at"]
    search_fields = ["source_topic__name", "target_topic__name"]
    readonly_fields = ["id", "created_at"]
    ordering = ["-similarity_score"]

    fieldsets = (
        (
            "Relation",
            {"fields": ("id", "source_topic", "relation_type", "target_topic")},
        ),
        (
            "Metadata",
            {"fields": ("similarity_score", "is_auto_detected")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at",), "classes": ("collapse",)},
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CROSS REFERENCE
# ─────────────────────────────────────────────────────────────────────────────


@admin.register(CrossReference)
class CrossReferenceAdmin(admin.ModelAdmin):  # type: ignore
    """Admin interface for CrossReference — See Also article links."""

    list_display = [
        "source_article",
        "ref_type",
        "target_article",
        "display_label",
        "created_at",
    ]
    list_filter = ["ref_type", "created_at"]
    search_fields = [
        "source_content__topic__name",
        "target_content__topic__name",
        "ref_text",
        "display_label",
    ]
    readonly_fields = ["id", "created_at"]
    ordering = ["ref_type", "-created_at"]

    fieldsets = (
        (
            "Cross Reference",
            {"fields": ("id", "source_content", "ref_type", "target_content")},
        ),
        (
            "Labels",
            {"fields": ("ref_text", "display_label")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at",), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="Source Article")
    def source_article(self, obj: CrossReference) -> str:
        return obj.source_content.topic.name

    @admin.display(description="Target Article")
    def target_article(self, obj: CrossReference) -> str:
        return obj.target_content.topic.name


# ─────────────────────────────────────────────────────────────────────────────
# CONTENT MEDIA
# ─────────────────────────────────────────────────────────────────────────────


@admin.register(ContentMedia)
class ContentMediaAdmin(admin.ModelAdmin):  # type: ignore
    """Admin interface for ContentMedia — images, diagrams, placeholders."""

    list_display = [
        "content",
        "media_type",
        "position",
        "display_order",
        "has_cloudinary",
        "has_youtube",
        "created_at",
    ]
    list_filter = ["media_type", "position", "created_at"]
    search_fields = ["content__topic__name", "caption", "alt_text"]
    readonly_fields = ["id", "created_at"]
    ordering = ["content", "display_order"]

    fieldsets = (
        (
            "Article",
            {"fields": ("id", "content", "media_type", "position", "display_order")},
        ),
        (
            "Asset URLs",
            {"fields": ("cloudinary_url", "youtube_url")},
        ),
        (
            "Display",
            {"fields": ("caption", "alt_text", "position_marker")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at",), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="Cloudinary", boolean=True)
    def has_cloudinary(self, obj: ContentMedia) -> bool:
        return bool(obj.cloudinary_url)

    @admin.display(description="YouTube", boolean=True)
    def has_youtube(self, obj: ContentMedia) -> bool:
        return bool(obj.youtube_url)


# ─────────────────────────────────────────────────────────────────────────────
# GENERATION LOG
# ─────────────────────────────────────────────────────────────────────────────


@admin.register(GenerationLog)
class GenerationLogAdmin(admin.ModelAdmin):  # type: ignore
    """Admin interface for GenerationLog — crash-recovery audit trail."""

    list_display = [
        "topic_name",
        "subject_name",
        "status",
        "quality_score",
        "word_count",
        "nodes_created",
        "generation_time_seconds",
        "created_at",
    ]
    list_filter = ["status", "subject_name", "created_at"]
    search_fields = ["topic_name", "subject_name", "error_message"]
    readonly_fields = [
        "id",
        "topic_name",
        "subject_name",
        "status",
        "nodes_created",
        "relations_created",
        "cross_refs_created",
        "quality_score",
        "word_count",
        "generation_time_seconds",
        "error_message",
        "created_at",
    ]
    ordering = ["-created_at"]

    fieldsets = (
        (
            "Run Info",
            {"fields": ("id", "topic_name", "subject_name", "status")},
        ),
        (
            "Output Stats",
            {
                "fields": (
                    "nodes_created",
                    "relations_created",
                    "cross_refs_created",
                    "quality_score",
                    "word_count",
                    "generation_time_seconds",
                )
            },
        ),
        (
            "Error Detail",
            {"fields": ("error_message",), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at",), "classes": ("collapse",)},
        ),
    )

    def has_add_permission(self, request: Any) -> bool:
        """Generation logs are system-generated — block manual creation."""
        return False

    def has_change_permission(self, request: Any, obj: Any = None) -> bool:
        """Generation logs are immutable — block edits."""
        return False
