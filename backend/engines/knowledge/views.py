"""
Knowledge Engine Views
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
import structlog

from engines.knowledge.models import (
    Program,
    Subject,
    Module,
    Topic,
    ChunkTopicMap,
    Theme,
)
from engines.knowledge.serializers import (
    ProgramSerializer,
    SubjectSerializer,
    ModuleSerializer,
    TopicSerializer,
    ChunkTopicMapSerializer,
    ThemeSerializer,
)
from engines.content.pagination import ContentCursorPagination
from engines.knowledge.services.mapping_service import MappingService
from engines.knowledge.services.search_service import SearchService

logger = structlog.get_logger(__name__)


class ProgramViewSet(viewsets.ModelViewSet):
    """ViewSet for Program CRUD."""

    queryset = Program.objects.all()
    serializer_class = ProgramSerializer
    permission_classes = [AllowAny]
    pagination_class = ContentCursorPagination

    def get_queryset(self):
        """Filter programs."""
        queryset = Program.objects.all()

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        return queryset.order_by("name")


class SubjectViewSet(viewsets.ModelViewSet):
    """ViewSet for Subject CRUD."""

    queryset = Subject.objects.select_related("program").all()
    serializer_class = SubjectSerializer
    permission_classes = [AllowAny]
    pagination_class = ContentCursorPagination

    def get_queryset(self):
        """Filter subjects."""
        queryset = Subject.objects.select_related("program").all()

        program_id = self.request.query_params.get("program_id")
        if program_id:
            queryset = queryset.filter(program_id=program_id)

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        return queryset.order_by("program", "order_index")


class ModuleViewSet(viewsets.ModelViewSet):
    """ViewSet for Module CRUD."""

    queryset = Module.objects.select_related("subject__program").all()
    serializer_class = ModuleSerializer
    permission_classes = [AllowAny]
    pagination_class = ContentCursorPagination

    def get_queryset(self):
        """Filter modules."""
        queryset = Module.objects.select_related("subject__program").all()

        subject_id = self.request.query_params.get("subject_id")
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        return queryset.order_by("subject", "order_index")


class TopicViewSet(viewsets.ModelViewSet):
    """ViewSet for Topic CRUD."""

    queryset = Topic.objects.select_related("module__subject", "subject").all()
    serializer_class = TopicSerializer
    permission_classes = [AllowAny]
    pagination_class = ContentCursorPagination

    def get_queryset(self):
        """Filter topics."""
        queryset = Topic.objects.select_related("module__subject", "subject").all()

        module_id = self.request.query_params.get("module_id")
        if module_id:
            queryset = queryset.filter(module_id=module_id)

        subject_id = self.request.query_params.get("subject_id")
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)

        difficulty = self.request.query_params.get("difficulty")
        if difficulty:
            queryset = queryset.filter(difficulty_level=difficulty)

        topic_type = self.request.query_params.get("type")
        if topic_type:
            queryset = queryset.filter(topic_type=topic_type)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(name__icontains=search)

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        return queryset.order_by("module", "order_index")

    @action(detail=True, methods=["get"])
    def chunks(self, request, pk=None):
        """Get all chunks mapped to this topic."""
        topic = self.get_object()
        mappings = topic.chunk_mappings.select_related("chunk").order_by(
            "-relevance_score"
        )

        serializer = ChunkTopicMapSerializer(mappings, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="auto-suggest-chunks")
    def auto_suggest_chunks(self, request, pk=None):
        """
        Auto-suggest relevant chunks for this topic using AI.

        POST /api/v1/knowledge/topics/{id}/auto-suggest-chunks/
        Query params: ?limit=20

        Returns: List of suggested chunks with relevance scores
        """
        topic = self.get_object()

        limit = int(request.query_params.get("limit", 20))
        limit = min(limit, 50)  # Max 50

        try:
            suggestions = MappingService.auto_suggest_chunks(
                topic_id=str(topic.id), limit=limit
            )

            logger.info(
                "auto_suggest_requested",
                topic_id=str(topic.id),
                user_id=request.user.id,
                suggestions_count=len(suggestions),
            )

            return Response(
                {
                    "topic_id": str(topic.id),
                    "topic_name": topic.name,
                    "suggestions": suggestions,
                    "count": len(suggestions),
                }
            )

        except Exception as e:
            logger.error("auto_suggest_failed", topic_id=str(topic.id), error=str(e))
            return Response(
                {"error": "Auto-suggest failed", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"], url_path="approve-mappings")
    def approve_mappings(self, request, pk=None):
        """
        Approve and create chunk-topic mappings.

        POST /api/v1/knowledge/topics/{id}/approve-mappings/
        Body: {
            "chunk_ids": ["uuid1", "uuid2", ...],
            "priority": 1
        }

        Returns: Created mappings count
        """
        topic = self.get_object()

        chunk_ids = request.data.get("chunk_ids", [])
        priority = request.data.get("priority", 1)

        if not chunk_ids:
            return Response(
                {"error": "chunk_ids required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            result = MappingService.approve_mappings(
                topic_id=str(topic.id),
                chunk_ids=chunk_ids,
                user_id=request.user.id,
                priority=priority,
            )

            logger.info(
                "mappings_approved",
                topic_id=str(topic.id),
                user_id=request.user.id,
                created=result["created"],
            )

            return Response(result, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(
                "approve_mappings_failed", topic_id=str(topic.id), error=str(e)
            )
            return Response(
                {"error": "Approval failed", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ChunkTopicMapViewSet(viewsets.ModelViewSet):
    """ViewSet for ChunkTopicMap CRUD."""

    queryset = ChunkTopicMap.objects.select_related("chunk", "topic").all()
    serializer_class = ChunkTopicMapSerializer
    permission_classes = [AllowAny]
    pagination_class = ContentCursorPagination

    def get_queryset(self):
        """Filter mappings."""
        queryset = ChunkTopicMap.objects.select_related("chunk", "topic").all()

        topic_id = self.request.query_params.get("topic_id")
        if topic_id:
            queryset = queryset.filter(topic_id=topic_id)

        chunk_id = self.request.query_params.get("chunk_id")
        if chunk_id:
            queryset = queryset.filter(chunk_id=chunk_id)

        auto_mapped = self.request.query_params.get("auto_mapped")
        if auto_mapped is not None:
            queryset = queryset.filter(auto_mapped=auto_mapped.lower() == "true")

        return queryset.order_by("-relevance_score")


class ThemeViewSet(viewsets.ModelViewSet):
    """ViewSet for Theme CRUD."""

    queryset = Theme.objects.all()
    serializer_class = ThemeSerializer
    permission_classes = [AllowAny]
    pagination_class = ContentCursorPagination

    def get_queryset(self):
        """Filter themes."""
        queryset = Theme.objects.all()

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(name__icontains=search)

        return queryset.order_by("name")

    @action(detail=True, methods=["get"])
    def topics(self, request, pk=None):
        """Get all topics in this theme."""
        theme = self.get_object()
        topics = theme.topics.all()
        serializer = TopicSerializer(topics, many=True)
        return Response(serializer.data)


class SearchViewSet(viewsets.ViewSet):
    """
    Unified Semantic Search across all content.
    GET /api/v1/knowledge/search/?q=...
    """

    permission_classes = [AllowAny]

    def list(self, request):
        query = request.query_params.get("q", "").strip()
        if not query or len(query) < 2:
            return Response([])

        limit = int(request.query_params.get("limit", 10))

        # Use our Unified Search Service
        results = SearchService.semantic_search(
            query=query, limit=limit, user=request.user
        )

        return Response(results)
