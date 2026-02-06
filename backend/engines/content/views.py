"""
Content Engine Views
"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Q
import structlog

from engines.content.models import (
    Document,
    Chunk,
    Embedding,
    Asset,
    IngestionJob
)
from engines.content.serializers import (
    DocumentSerializer,
    DocumentUploadSerializer,
    ChunkSerializer,
    ChunkListSerializer,
    EmbeddingSerializer,
    AssetSerializer,
    IngestionJobSerializer
)
from engines.content.services.ingestion_service import IngestionService
from engines.content.pagination import ContentCursorPagination, ChunkCursorPagination

logger = structlog.get_logger(__name__)


class DocumentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Document CRUD operations.
    """
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ContentCursorPagination
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter documents by query parameters."""
        queryset = Document.objects.all()
        
        # Filter by source_type
        source_type = self.request.query_params.get('source_type')
        if source_type:
            queryset = queryset.filter(source_type=source_type)
        
        # Filter by source_edition
        source_edition = self.request.query_params.get('source_edition')
        if source_edition:
            queryset = queryset.filter(source_edition__icontains=source_edition)
        
        # Search by title
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(title__icontains=search)
        
        return queryset.order_by('-created_at')
    
    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload(self, request):
        """
        Upload and ingest a new document.
        
        POST /api/v1/content/documents/upload/
        """
        serializer = DocumentUploadSerializer(data=request.data)
        
        if not serializer.is_valid():
            logger.warning("upload_validation_failed", errors=serializer.errors)
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Ingest document
            result = IngestionService.ingest_document(
                file=serializer.validated_data['file'],
                title=serializer.validated_data['title'],
                source_type=serializer.validated_data['source_type'],
                source_edition=serializer.validated_data.get('source_edition'),
                metadata=serializer.validated_data.get('metadata', {})
            )
            
            logger.info(
                "document_uploaded",
                document_id=result['document_id'],
                user_id=request.user.id
            )
            
            return Response(result, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error("document_upload_failed", error=str(e))
            return Response(
                {'error': 'Upload failed', 'message': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def chunks(self, request, pk=None):
        """
        Get all chunks for a document.
        
        GET /api/v1/content/documents/{id}/chunks/
        """
        document = self.get_object()
        chunks = document.chunks.all()
        serializer = ChunkListSerializer(chunks, many=True)
        
        return Response(serializer.data)


class ChunkViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Chunk read operations.
    """
    queryset = Chunk.objects.all()
    permission_classes = [IsAuthenticated]
    pagination_class = ChunkCursorPagination
    ordering = ['document', 'chunk_index']
    
    def get_serializer_class(self):
        """Use lightweight serializer for list, full for detail."""
        if self.action == 'list':
            return ChunkListSerializer
        return ChunkSerializer
    
    def get_queryset(self):
        """Filter chunks by query parameters."""
        queryset = Chunk.objects.select_related('document').all()
        
        # Filter by document
        document_id = self.request.query_params.get('document_id')
        if document_id:
            queryset = queryset.filter(document_id=document_id)
        
        # Filter by source_type
        source_type = self.request.query_params.get('source_type')
        if source_type:
            queryset = queryset.filter(source_type=source_type)
        
        # Filter by chapter
        chapter = self.request.query_params.get('chapter')
        if chapter:
            queryset = queryset.filter(chapter_name__icontains=chapter)
        
        # Filter by quality
        quality = self.request.query_params.get('quality')
        if quality:
            queryset = queryset.filter(quality_flag=quality)
        
        # Search in chunk text
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(chunk_text__icontains=search)
        
        return queryset.order_by('document', 'chunk_index')


class EmbeddingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Embedding read operations.
    """
    queryset = Embedding.objects.all()
    serializer_class = EmbeddingSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ContentCursorPagination
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter embeddings by query parameters."""
        queryset = Embedding.objects.all()
        
        # Filter by content_type
        content_type = self.request.query_params.get('content_type')
        if content_type:
            queryset = queryset.filter(content_type=content_type)
        
        # Filter by content_id
        content_id = self.request.query_params.get('content_id')
        if content_id:
            queryset = queryset.filter(content_id=content_id)
        
        return queryset.order_by('-created_at')


class AssetViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Asset read operations.
    """
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ContentCursorPagination
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter assets by query parameters."""
        queryset = Asset.objects.select_related('chunk').all()
        
        # Filter by chunk
        chunk_id = self.request.query_params.get('chunk_id')
        if chunk_id:
            queryset = queryset.filter(chunk_id=chunk_id)
        
        # Filter by asset_type
        asset_type = self.request.query_params.get('asset_type')
        if asset_type:
            queryset = queryset.filter(asset_type=asset_type)
        
        return queryset.order_by('-created_at')


class IngestionJobViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for IngestionJob monitoring.
    """
    queryset = IngestionJob.objects.all()
    serializer_class = IngestionJobSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ContentCursorPagination
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter jobs by query parameters."""
        queryset = IngestionJob.objects.select_related('document').all()
        
        # Filter by status
        job_status = self.request.query_params.get('status')
        if job_status:
            queryset = queryset.filter(status=job_status)
        
        # Filter by document
        document_id = self.request.query_params.get('document_id')
        if document_id:
            queryset = queryset.filter(document_id=document_id)
        
        return queryset.order_by('-created_at')
        