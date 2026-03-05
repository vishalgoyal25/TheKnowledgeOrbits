"""
Knowledge Engine Admin Interface
"""

from typing import Any

from django.contrib import admin

from engines.knowledge.models import (
    ChunkRelation,
    ChunkTopicMap,
    Module,
    Program,
    Subject,
    Theme,
    ThemeTopicMap,
    Topic,
)


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):  # type: ignore
    """Admin interface for Program."""

    list_display = ["name", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["id", "created_at", "updated_at"]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "description", "is_active")}),
        ("Exam Pattern", {"fields": ("exam_pattern",), "classes": ("collapse",)}),
        (
            "System Information",
            {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):  # type: ignore
    """Admin interface for Subject."""

    list_display = ["name", "program", "order_index", "is_active", "created_at"]
    list_filter = ["program", "is_active", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["program", "order_index"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "program", "description", "order_index", "is_active")},
        ),
        (
            "System Information",
            {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):  # type: ignore
    """Admin interface for Module."""

    list_display = ["name", "subject", "order_index", "is_active", "created_at"]
    list_filter = ["subject__program", "subject", "is_active", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["subject", "order_index"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "subject", "description", "order_index", "is_active")},
        ),
        (
            "System Information",
            {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):  # type: ignore
    """Admin interface for Topic."""

    list_display = [
        "name",
        "module",
        "topic_type",
        "difficulty_level",
        "order_index",
        "is_active",
        "created_at",
    ]
    list_filter = [
        "module__subject__program",
        "module__subject",
        "topic_type",
        "difficulty_level",
        "is_active",
        "created_at",
    ]
    search_fields = ["name", "description", "keywords"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["module", "order_index"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "module", "subject", "parent_topic", "description")},
        ),
        (
            "Classification",
            {"fields": ("topic_type", "difficulty_level", "order_index", "is_active")},
        ),
        ("AI Mapping", {"fields": ("keywords",), "classes": ("collapse",)}),
        (
            "System Information",
            {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_urls(self) -> Any:
        from django.urls import path

        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/suggest-chunks/",
                self.admin_site.admin_view(self.suggest_chunks_view),
                name="knowledge_topic_suggest",
            ),
        ]
        return custom_urls + urls

    def suggest_chunks_view(self, request, object_id) -> Any:  # type: ignore
        """Custom admin view for suggesting chunks."""
        from django.shortcuts import render

        from engines.knowledge.services.mapping_service import MappingService

        topic = self.get_object(request, object_id)
        if topic is None:
            from django.http import Http404

            raise Http404("Topic not found")

        if request.method == "POST":
            # Get suggested chunk IDs from form
            chunk_ids = request.POST.getlist("chunk_ids")

            if chunk_ids:
                result = MappingService.approve_mappings(
                    topic_id=str(topic.id),
                    chunk_ids=chunk_ids,
                    user_id=request.user.id,
                    priority=1,
                )

                self.message_user(
                    request,
                    f"Successfully mapped {result['created']} chunks to {topic.name}",
                )

        # Get suggestions
        suggestions = MappingService.auto_suggest_chunks(
            topic_id=str(topic.id),
            limit=20,
        )

        context = {
            "topic": topic,
            "suggestions": suggestions,
            "opts": self.model._meta,
        }

        return render(request, "admin/knowledge/suggest_chunks.html", context)


@admin.register(ChunkTopicMap)
class ChunkTopicMapAdmin(admin.ModelAdmin):  # type: ignore
    """Admin interface for ChunkTopicMap."""

    list_display = [
        "topic",
        "chunk_preview",
        "relevance_score",
        "priority",
        "auto_mapped",
        "created_at",
    ]
    list_filter = ["priority", "auto_mapped", "created_at"]
    search_fields = ["topic__name", "chunk__chunk_text"]
    readonly_fields = ["id", "created_at"]
    ordering = ["-relevance_score"]

    @admin.display(description="Chunk Preview")
    def chunk_preview(self, obj) -> Any:  # type: ignore
        """Show chunk text preview."""
        return (
            obj.chunk.chunk_text[:100] + "..."
            if len(obj.chunk.chunk_text) > 100
            else obj.chunk.chunk_text
        )


@admin.register(Theme)
class ThemeAdmin(admin.ModelAdmin):  # type: ignore
    """Admin interface for Theme."""

    list_display = ["name", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(ThemeTopicMap)
class ThemeTopicMapAdmin(admin.ModelAdmin):  # type: ignore
    """Admin interface for ThemeTopicMap."""

    list_display = ["theme", "topic", "weight", "created_at"]
    list_filter = ["theme", "created_at"]
    search_fields = ["theme__name", "topic__name"]
    readonly_fields = ["id", "created_at"]
    ordering = ["-weight"]


@admin.register(ChunkRelation)
class ChunkRelationAdmin(admin.ModelAdmin):  # type: ignore
    """Admin interface for ChunkRelation."""

    list_display = [
        "chunk_1_preview",
        "relation_type",
        "chunk_2_preview",
        "similarity_score",
        "created_at",
    ]
    list_filter = ["relation_type", "created_at"]
    readonly_fields = ["id", "created_at"]

    @admin.display(description="Chunk 1")
    def chunk_1_preview(self, obj) -> Any:  # type: ignore
        """Show chunk 1 preview."""
        return f"Chunk #{obj.chunk_1.chunk_index}"

    @admin.display(description="Chunk 2")
    def chunk_2_preview(self, obj) -> Any:  # type: ignore
        """Show chunk 2 preview."""
        return f"Chunk #{obj.chunk_2.chunk_index}"
