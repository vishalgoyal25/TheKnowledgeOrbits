from django.contrib import admin

from .models import Asset, Chunk, Document, Embedding, IngestionJob


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):  # type: ignore
    list_display = (
        "title",
        "source_type",
        "source_edition",
        "publication_year",
        "created_at",
    )
    list_filter = ("source_type", "publication_year", "created_at")
    search_fields = ("title", "id", "source_edition")
    date_hierarchy = "created_at"
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):  # type: ignore
    list_display = (
        "__str__",
        "document",
        "source_type",
        "page_number",
        "quality_flag",
        "confidence_score",
    )
    list_filter = ("source_type", "quality_flag", "created_at")
    search_fields = ("chunk_text", "document__title")
    raw_id_fields = ("document",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Embedding)
class EmbeddingAdmin(admin.ModelAdmin):  # type: ignore
    list_display = ("__str__", "model_name", "created_at")
    list_filter = ("content_type", "model_name")
    search_fields = ("content_id",)
    readonly_fields = ("id", "created_at", "vector")


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):  # type: ignore
    list_display = ("__str__", "asset_type", "created_at")
    list_filter = ("asset_type", "created_at")
    search_fields = ("chunk__document__title",)
    raw_id_fields = ("chunk",)
    readonly_fields = ("id", "created_at")


@admin.register(IngestionJob)
class IngestionJobAdmin(admin.ModelAdmin):  # type: ignore
    list_display = (
        "__str__",
        "status",
        "progress_percentage",
        "created_at",
        "completed_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("document__title", "error_log")
    raw_id_fields = ("document",)
    readonly_fields = (
        "id",
        "created_at",
        "started_at",
        "completed_at",
        "progress_percentage",
    )
