import sentry_sdk

"""
Content Engine Views
"""

from typing import Any, Optional, cast

from django.db.models import QuerySet

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

import structlog

from core.pagination import StandardPageNumberPagination
from engines.auth.models import User
from engines.authorization.permissions import CanManageContent
from engines.content.models import Asset, Chunk, Document, Embedding, IngestionJob
from engines.content.serializers import (
    AssetSerializer,
    ChunkListSerializer,
    ChunkSerializer,
    DocumentSerializer,
    DocumentUploadSerializer,
    EmbeddingSerializer,
    IngestionJobSerializer,
)
from engines.content.services.ingestion_service import IngestionService

logger = structlog.get_logger(__name__)


class DocumentViewSet(viewsets.ModelViewSet):  # type: ignore
    """
    ViewSet for Document CRUD operations.
    """

    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPageNumberPagination
    ordering = ["-created_at"]

    def get_queryset(self) -> QuerySet:  # type: ignore
        """
        Filter documents by query parameters (source_type, source_edition, search).

        Returns:
            QuerySet[Document]: Filtered and ordered document collection.
        """
        queryset = Document.objects.all()

        # Filter by source_type
        source_type = self.request.query_params.get("source_type")
        if source_type:
            queryset = queryset.filter(source_type=source_type)

        # Filter by source_edition
        source_edition = self.request.query_params.get("source_edition")
        if source_edition:
            queryset = queryset.filter(source_edition__icontains=source_edition)

        # Search by title
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(title__icontains=search)

        return queryset.order_by("-created_at")

    @action(
        detail=False,
        methods=["post"],
        parser_classes=[MultiPartParser, FormParser],
        permission_classes=[CanManageContent],
    )
    def upload(self, request: Request) -> Response:
        """
        Upload and ingest a new document (PDF/Text) into the Knowledge Orbit.

        This invokes the full orchestration pipeline.

        POST /api/v1/content/documents/upload/
        """
        serializer = DocumentUploadSerializer(data=request.data)

        if not serializer.is_valid():
            logger.warning("upload_validation_failed", errors=serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Ingest document
            result = IngestionService.ingest_document(
                file=serializer.validated_data["file"],
                title=serializer.validated_data["title"],
                source_type=serializer.validated_data["source_type"],
                source_edition=serializer.validated_data.get("source_edition"),
                metadata=serializer.validated_data.get("metadata", {}),
            )

            user = cast(User, request.user)
            logger.info(
                "document_uploaded",
                document_id=result["document_id"],
                user_id=user.id,
            )

            return Response(result, status=status.HTTP_201_CREATED)

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error("document_upload_failed", error=str(e), exc_info=True)
            return Response(
                {
                    "error": "Upload failed",
                    "message": "An error occurred during document ingestion.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"])
    def chunks(self, request: Request, pk: Optional[str] = None) -> Response:
        """
        Get all chunks for a specific document with ordered sequence.

        GET /api/v1/content/documents/{id}/chunks/
        """
        document = self.get_object()
        chunks = document.chunks.all()
        serializer = ChunkListSerializer(chunks, many=True)

        return Response(serializer.data)


class ChunkViewSet(viewsets.ReadOnlyModelViewSet):  # type: ignore
    """
    ViewSet for Chunk read operations.
    """

    queryset = Chunk.objects.all()
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPageNumberPagination
    ordering = ["document", "chunk_index"]

    def get_serializer_class(self) -> Any:
        """Use lightweight serializer for list, full for detail or if content requested."""
        if self.action == "list":
            # Allow forcing full serializer via query param
            if self.request.query_params.get("include_content") == "true":
                return ChunkSerializer
            return ChunkListSerializer
        return ChunkSerializer

    def get_queryset(self) -> Any:
        """Filter chunks by query parameters."""
        queryset = Chunk.objects.select_related("document").all()

        # Filter by document
        document_id = self.request.query_params.get("document_id")
        if document_id:
            queryset = queryset.filter(document_id=document_id)

        # Filter by source_type
        source_type = self.request.query_params.get("source_type")
        if source_type:
            queryset = queryset.filter(source_type=source_type)

        # Filter by chapter
        chapter = self.request.query_params.get("chapter")
        if chapter:
            queryset = queryset.filter(chapter_name__icontains=chapter)

        # Filter by quality
        quality = self.request.query_params.get("quality")
        if quality:
            queryset = queryset.filter(quality_flag=quality)

        # Search in chunk text
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(chunk_text__icontains=search)

        # Filter by start_index (for deep linking/reading)
        start_index = self.request.query_params.get("start_index")
        if start_index:
            try:
                queryset = queryset.filter(chunk_index__gte=int(start_index))
            except (ValueError, TypeError):
                pass

        return queryset.order_by("document", "chunk_index")


class EmbeddingViewSet(viewsets.ReadOnlyModelViewSet):  # type: ignore
    """
    ViewSet for Embedding read operations.
    """

    queryset = Embedding.objects.all()
    serializer_class = EmbeddingSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPageNumberPagination
    ordering = ["-created_at"]

    def get_queryset(self) -> Any:
        """Filter embeddings by query parameters."""
        queryset = Embedding.objects.all()

        # Filter by content_type
        content_type = self.request.query_params.get("content_type")
        if content_type:
            queryset = queryset.filter(content_type=content_type)

        # Filter by content_id
        content_id = self.request.query_params.get("content_id")
        if content_id:
            queryset = queryset.filter(content_id=content_id)

        return queryset.order_by("-created_at")


class AssetViewSet(viewsets.ReadOnlyModelViewSet):  # type: ignore
    """
    ViewSet for Asset read operations.
    """

    queryset = Asset.objects.all()
    serializer_class = AssetSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPageNumberPagination
    ordering = ["-created_at"]

    def get_queryset(self) -> Any:
        """Filter assets by query parameters."""
        queryset = Asset.objects.select_related("chunk").all()

        # Filter by chunk
        chunk_id = self.request.query_params.get("chunk_id")
        if chunk_id:
            queryset = queryset.filter(chunk_id=chunk_id)

        # Filter by asset_type
        asset_type = self.request.query_params.get("asset_type")
        if asset_type:
            queryset = queryset.filter(asset_type=asset_type)

        return queryset.order_by("-created_at")


class IngestionJobViewSet(viewsets.ReadOnlyModelViewSet):  # type: ignore
    """
    ViewSet for IngestionJob monitoring.
    """

    queryset = IngestionJob.objects.all()
    serializer_class = IngestionJobSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPageNumberPagination
    ordering = ["-created_at"]

    def get_queryset(self) -> Any:
        """Filter jobs by query parameters."""
        queryset = IngestionJob.objects.select_related("document").all()

        # Filter by status
        job_status = self.request.query_params.get("status")
        if job_status:
            queryset = queryset.filter(status=job_status)

        # Filter by document
        document_id = self.request.query_params.get("document_id")
        if document_id:
            queryset = queryset.filter(document_id=document_id)

        return queryset.order_by("-created_at")
