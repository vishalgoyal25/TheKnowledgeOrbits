"""Content Engine Serializers."""

from rest_framework import serializers

from engines.content.models import Asset, Chunk, Document, Embedding, IngestionJob


class DocumentSerializer(serializers.ModelSerializer):  # type: ignore
    """Serializer for Document model."""

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "file_path",
            "source_type",
            "source_edition",
            "source_version",
            "isbn",
            "publication_year",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class DocumentUploadSerializer(serializers.Serializer):  # type: ignore
    """Serializer for document upload request."""

    file = serializers.FileField(required=True)
    title = serializers.CharField(max_length=500, required=True)
    source_type = serializers.ChoiceField(choices=["static", "dynamic"], required=True)
    source_edition = serializers.CharField(
        max_length=50, required=False, allow_blank=True
    )
    source_version = serializers.CharField(
        max_length=20, required=False, allow_blank=True
    )
    isbn = serializers.CharField(max_length=20, required=False, allow_blank=True)
    publication_year = serializers.IntegerField(
        required=False, allow_null=True, min_value=1900, max_value=2100
    )
    metadata = serializers.JSONField(required=False, default=dict)


class ChunkSerializer(serializers.ModelSerializer):  # type: ignore
    """Serializer for Chunk model."""

    document_title = serializers.CharField(source="document.title", read_only=True)

    class Meta:
        model = Chunk
        fields = [
            "id",
            "chunk_text",
            "chunk_index",
            "page_number",
            "source_type",
            "document",
            "document_title",
            "chapter_name",
            "quality_flag",
            "confidence_score",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ChunkListSerializer(serializers.ModelSerializer):  # type: ignore
    """Lightweight serializer for chunk listing."""

    document_title = serializers.CharField(source="document.title", read_only=True)

    class Meta:
        model = Chunk
        fields = [
            "id",
            "chunk_index",
            "page_number",
            "chapter_name",
            "document_title",
            "quality_flag",
            "created_at",
        ]


class EmbeddingSerializer(serializers.ModelSerializer):  # type: ignore
    """Serializer for Embedding model."""

    class Meta:
        model = Embedding
        fields = [
            "id",
            "content_type",
            "content_id",
            "vector",
            "model_name",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class AssetSerializer(serializers.ModelSerializer):  # type: ignore
    """Serializer for Asset model."""

    class Meta:
        model = Asset
        fields = ["id", "chunk", "asset_type", "asset_url", "metadata", "created_at"]
        read_only_fields = ["id", "created_at"]


class IngestionJobSerializer(serializers.ModelSerializer):  # type: ignore
    """Serializer for IngestionJob model."""

    document_title = serializers.CharField(
        source="document.title", read_only=True, allow_null=True
    )
    progress_percentage = serializers.FloatField(read_only=True)

    class Meta:
        model = IngestionJob
        fields = [
            "id",
            "document",
            "document_title",
            "status",
            "error_log",
            "total_pages",
            "processed_pages",
            "chunks_created",
            "progress_percentage",
            "started_at",
            "completed_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "error_log",
            "progress_percentage",
            "created_at",
        ]
