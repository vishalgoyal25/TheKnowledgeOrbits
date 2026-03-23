import sentry_sdk

"""
Knowledge Engine Views
"""

from typing import Any, Optional, cast

from django.db.models import QuerySet

from rest_framework import status, viewsets, views
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

import structlog

from core.pagination import StandardPageNumberPagination
from engines.auth.models import User
from engines.knowledge.models import (
    ChunkTopicMap,
    Module,
    Program,
    Subject,
    Theme,
    Topic,
)
from engines.knowledge.serializers import (
    ChunkTopicMapSerializer,
    ModuleListSerializer,
    ModuleSerializer,
    ProgramListSerializer,
    ProgramSerializer,
    SubjectListSerializer,
    SubjectSerializer,
    ThemeSerializer,
    TopicListSerializer,
    TopicSerializer,
)
from engines.knowledge.services.mapping_service import MappingService
from engines.knowledge.services.search_service import SearchService
from engines.shared.services.cache_service import get_cache_service

logger = structlog.get_logger(__name__)
cache_service = get_cache_service()


class ProgramViewSet(viewsets.ModelViewSet):  # type: ignore
    """ViewSet for Program CRUD."""

    queryset = Program.objects.all()
    serializer_class = ProgramSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardPageNumberPagination

    def get_serializer_class(self):
        if self.action == "list":
            return ProgramListSerializer
        return ProgramSerializer

    def get_queryset(self) -> QuerySet:  # type: ignore
        """
        Filter programs by activation status and ordering.

        Returns:
            QuerySet[Program]: Ordered collection of programs.
        """
        queryset = Program.objects.all()

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        return queryset.order_by("name")

    def list(self, request, *args, **kwargs):
        """Cache the programs list for all users (public data)."""
        cache_key = "programs_list"
        cached = cache_service.get(cache_key)
        if cached:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache_service.set(cache_key, response.data, 3600)  # 1 hour
        return response


class SubjectViewSet(viewsets.ModelViewSet):  # type: ignore
    """ViewSet for Subject CRUD."""

    queryset = Subject.objects.select_related("program").all()
    serializer_class = SubjectSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardPageNumberPagination

    def get_serializer_class(self):
        if self.action == "list":
            return SubjectListSerializer
        return SubjectSerializer

    def get_queryset(self) -> QuerySet:  # type: ignore
        """
        Filter subjects by program and activation status.

        Returns:
            QuerySet[Subject]: Filtered collection of subjects.
        """
        queryset = Subject.objects.select_related("program").all()

        if self.action == "list":
            queryset = queryset.defer("description")

        program_id = self.request.query_params.get("program_id")
        if program_id:
            queryset = queryset.filter(program_id=program_id)

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        return queryset.order_by("program", "order_index")

    def list(self, request, *args, **kwargs):
        """Cache the subjects list for all users (public data)."""
        params = request.query_params.urlencode()
        cache_key = f"subjects_list_{params}"
        cached = cache_service.get(cache_key)
        if cached:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache_service.set(cache_key, response.data, 3600)  # 1 hour
        return response


class ModuleViewSet(viewsets.ModelViewSet):  # type: ignore
    """ViewSet for Module CRUD."""

    queryset = Module.objects.select_related("subject__program").all()
    serializer_class = ModuleSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardPageNumberPagination

    def get_serializer_class(self):
        if self.action == "list":
            return ModuleListSerializer
        return ModuleSerializer

    def get_queryset(self) -> Any:
        """Filter modules."""
        queryset = Module.objects.select_related("subject__program").all()

        if self.action == "list":
            queryset = queryset.defer("description")

        subject_id = self.request.query_params.get("subject_id")
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        return queryset.order_by("subject", "order_index")

    def list(self, request, *args, **kwargs):
        """Cache the modules list for all users (public data)."""
        params = request.query_params.urlencode()
        cache_key = f"modules_list_{params}"
        cached = cache_service.get(cache_key)
        if cached:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache_service.set(cache_key, response.data, 3600)  # 1 hour
        return response


class TopicViewSet(viewsets.ModelViewSet):  # type: ignore
    """ViewSet for Topic CRUD."""

    queryset = Topic.objects.select_related("module__subject", "subject").all()
    serializer_class = TopicSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardPageNumberPagination

    def get_serializer_class(self):
        if self.action == "list":
            return TopicListSerializer
        return TopicSerializer

    def get_queryset(self) -> QuerySet:  # type: ignore
        """
        Comprehensive filtering for topics across modules, subjects, and difficulty.

        Returns:
            QuerySet[Topic]: Filtered topic collection.
        """
        queryset = Topic.objects.select_related("module", "subject").all()

        if self.action == "list":
            # Defer heavy description field in list views
            queryset = queryset.defer("description")

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

        # Atomic Counter Caching for total topics count
        if (
            self.action == "list"
            and not any([module_id, subject_id, difficulty, topic_type, search])
            and (is_active is None or is_active.lower() == "true")
        ):
            cache_service.get_count("total_topics_count", queryset)

        return queryset.order_by("module", "order_index")

    def list(self, request, *args, **kwargs):
        """Cache the topics list for all users (public data)."""
        params = request.query_params.urlencode()
        cache_key = f"topics_list_{params}"
        cached = cache_service.get(cache_key)
        if cached:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache_service.set(cache_key, response.data, 900)  # 15 minutes
        return response

    @action(detail=True, methods=["get"])
    def chunks(self, request: Response, pk: Optional[str] = None) -> Response:
        """
        Retrieve all semantic chunks mapped to this topic, ordered by relevance.

        GET /api/v1/knowledge/topics/{id}/chunks/
        """
        topic = self.get_object()
        mappings = topic.chunk_mappings.select_related("chunk").order_by(
            "-relevance_score"
        )

        serializer = ChunkTopicMapSerializer(mappings, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        url_path="auto-suggest-chunks",
        permission_classes=[IsAuthenticated],
    )
    def auto_suggest_chunks(
        self, request: Request, pk: Optional[str] = None
    ) -> Response:
        """
        Invoke AI-powered mapping service to suggest relevant document chunks.

        POST /api/v1/knowledge/topics/{id}/auto-suggest-chunks/
        """
        topic = self.get_object()

        limit = int(request.query_params.get("limit", 20))
        limit = min(limit, 50)  # Max 50

        try:
            suggestions = MappingService.auto_suggest_chunks(
                topic_id=str(topic.id), limit=limit
            )

            user = cast(User, request.user)
            logger.info(
                "auto_suggest_requested",
                topic_id=str(topic.id),
                user_id=user.id,
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
            sentry_sdk.capture_exception(e)
            logger.error(
                "auto_suggest_failed",
                topic_id=str(topic.id),
                error=str(e),
                exc_info=True,
            )
            return Response(
                {
                    "error": "Auto-suggest failed",
                    "message": "An unexpected error occurred during suggestion generation.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(
        detail=True,
        methods=["post"],
        url_path="approve-mappings",
        permission_classes=[IsAuthenticated],
    )
    def approve_mappings(self, request: Request, pk: Optional[str] = None) -> Response:
        """
        Formalize suggested mappings into ChunkTopicMap records.

        POST /api/v1/knowledge/topics/{id}/approve-mappings/
        """
        topic = self.get_object()

        chunk_ids = request.data.get("chunk_ids", [])
        priority = request.data.get("priority", 1)

        if not chunk_ids:
            return Response(
                {"error": "chunk_ids required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = cast(User, request.user)
            result = MappingService.approve_mappings(
                topic_id=str(topic.id),
                chunk_ids=chunk_ids,
                user_id=str(user.id),
                priority=priority,
            )

            logger.info(
                "mappings_approved",
                topic_id=str(topic.id),
                user_id=user.id,
                created=result["created"],
            )

            return Response(result, status=status.HTTP_201_CREATED)

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(
                "approve_mappings_failed",
                topic_id=str(topic.id),
                error=str(e),
                exc_info=True,
            )
            return Response(
                {
                    "error": "Approval failed",
                    "message": "An error occurred while approving mappings.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ChunkTopicMapViewSet(viewsets.ModelViewSet):  # type: ignore
    """ViewSet for ChunkTopicMap CRUD."""

    queryset = ChunkTopicMap.objects.select_related("chunk", "topic").all()
    serializer_class = ChunkTopicMapSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardPageNumberPagination

    def get_queryset(self) -> Any:
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


class ThemeViewSet(viewsets.ModelViewSet):  # type: ignore
    """ViewSet for Theme CRUD."""

    queryset = Theme.objects.all()
    serializer_class = ThemeSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardPageNumberPagination

    def get_queryset(self) -> Any:
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
    def topics(self, request, pk=None) -> Any:  # type: ignore
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

    def list(self, request) -> Any:  # type: ignore
        query = request.query_params.get("q", "").strip()
        if not query or len(query) < 2:
            return Response([])

        limit = int(request.query_params.get("limit", 10))

        # Use our Unified Search Service
        results = SearchService.semantic_search(
            query=query, limit=limit, user=request.user
        )

        return Response(results)


class HierarchyListView(views.APIView):
    """
    Returns the complete, deeply nested UPSC hierarchy:
    Program -> Subjects -> Modules -> Topics -> SubTopics.
    Used for highly efficient populating of UI chained dropdowns in one network request.
    GET /api/v1/knowledge/hierarchy/
    """

    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        cache_key = "master_hierarchy_list_v3"  # bumped to bust stale cache
        cached = cache_service.get(cache_key)
        if cached:
            return Response(cached)

        programs = Program.objects.filter(is_active=True)
        response_data = []

        for p in programs:
            p_data = {"id": str(p.id), "name": p.name, "subjects": []}
            subjects = Subject.objects.filter(program=p, is_active=True).order_by(
                "order_index"
            )
            for s in subjects:
                s_data = {"id": str(s.id), "name": s.name, "modules": []}
                modules = Module.objects.filter(subject=s, is_active=True).order_by(
                    "order_index"
                )
                for m in modules:
                    m_data = {"id": str(m.id), "name": m.name, "topics": []}
                    # Return only top-level (root) topics.
                    # Children will be nested in sub_topics to prevent duplicates.
                    root_topics = Topic.objects.filter(
                        module=m, parent_topic__isnull=True, is_active=True
                    ).order_by("order_index")
                    for t in root_topics:
                        t_data = {"id": str(t.id), "name": t.name, "sub_topics": []}
                        sub_topics = Topic.objects.filter(
                            parent_topic=t, is_active=True
                        ).order_by("order_index")
                        for st in sub_topics:
                            t_data["sub_topics"].append(
                                {"id": str(st.id), "name": st.name}
                            )
                        m_data["topics"].append(t_data)
                    s_data["modules"].append(m_data)
                p_data["subjects"].append(s_data)
            response_data.append(p_data)

        cache_service.set(cache_key, response_data, 3600)  # 1 hour
        return Response(response_data)
