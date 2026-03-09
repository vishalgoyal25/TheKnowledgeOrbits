from typing import Any

import sentry_sdk

"""
Article Generation Engine Views
"""

import concurrent.futures

from django.core.cache import cache
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

import structlog

from core.pagination import StandardLimitOffsetPagination
from engines.shared.services.cache_service import get_cache_service
from engines.shared.services.visibility_service import get_visibility_service
from engines.userstate.services.activity_service import get_activity_service

from .models import Article, ArticleGenerationJob
from .serializers import (
    ArticleDetailSerializer,
    ArticleGenerationJobSerializer,
    ArticleGenerationRequestSerializer,
    ArticleListSerializer,
    ArticleSourceMapSerializer,
)
from .services.generation_service import ArticleGenerationService

logger = structlog.get_logger(__name__)
cache_service = get_cache_service()

# Global thread pool for background article generation
article_executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)


def _background_article_generation(
    job_id: str, topic_id: str, include_ca: bool, user_id: Any
):
    """Background task for article generation."""
    try:
        job = ArticleGenerationJob.objects.get(id=job_id)
        job.status = "processing"
        job.started_at = timezone.now()
        job.save()

        # Generate article
        result = ArticleGenerationService.generate_article(
            topic_id=topic_id, include_ca=include_ca, user_id=user_id
        )

        # Fetch generated article
        article = Article.objects.get(id=result["article_id"])

        # ===== OWNERSHIP LOGIC =====
        if user_id:
            from engines.auth.models import User

            user = User.objects.get(id=user_id)
            article.created_by = user
            article.is_public = False
            article.save()

            # Log activity
            activity_service = get_activity_service()
            activity_service.log_article_generated(
                user=user, article_id=str(article.id), topic_id=topic_id
            )
            cache.delete(f"dashboard_{user_id}")
        else:
            article.is_public = True
            article.created_by = None
            article.save()

        # Update Job
        job.status = "completed"
        job.article = article
        job.completed_at = timezone.now()
        job.save()
        logger.info(
            "background_article_generation_success",
            job_id=job_id,
            article_id=str(article.id),
        )

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.error(
            "background_article_generation_failed", job_id=job_id, error=str(e)
        )
        try:
            job = ArticleGenerationJob.objects.get(id=job_id)
            job.status = "failed"
            job.error_log = str(e)
            job.save()
        except Exception:
            pass


class ArticleViewSet(viewsets.ModelViewSet):  # type: ignore
    """
    ViewSet for Articles.

    - List: GET /api/v1/articles/
    - Detail: GET /api/v1/articles/:id/
    - Generate: POST /api/v1/articles/generate/
    - Sources: GET /api/v1/articles/:id/sources/
    - Delete: DELETE /api/v1/articles/:id/
    """

    permission_classes = [AllowAny]
    lookup_field = "id"
    pagination_class = StandardLimitOffsetPagination

    ordering_fields = ["created_at", "title", "review_status"]
    ordering = ["-created_at"]

    def get_queryset(self) -> Any:
        """
        Get articles.
        - Anonymous: Only is_published=True AND is_public=True
        - Logged-in: (is_published=True AND is_public=True) OR (created_by=user)
        """
        user = self.request.user
        if user.is_authenticated:
            # User can see all public published articles OR any article they created
            queryset = Article.objects.filter(
                Q(is_published=True, is_public=True) | Q(created_by=user)
            )
        else:
            # Anonymous see only public published
            queryset = Article.objects.filter(is_published=True, is_public=True)

        # Performance: Use atomic counter caching for total count
        # This replaces the expensive SELECT COUNT(*) fired by pagination
        if self.action == "list" and not any(
            self.request.query_params.get(p) for p in ["topic_id", "review_status"]
        ):
            cache_key = "total_articles_count"
            cache_service.get_count(cache_key, queryset)
            # Inject into pagination if standard paginator is used
            # StandardLimitOffsetPagination will still call count() unless we intercept
            # For now, we optimize the QuerySet itself
            pass

        queryset = queryset.select_related("topic", "topic__subject", "created_by")

        # Defer large content field for list views to improve performance
        if self.action in ["list", "my_notebook"]:
            queryset = queryset.defer("content")

        # Filter by topic
        topic_id = self.request.query_params.get("topic_id")
        if topic_id:
            queryset = queryset.filter(topic_id=topic_id)

        # Filter by review status
        review_status = self.request.query_params.get("review_status")
        if review_status:
            queryset = queryset.filter(review_status=review_status)

        return queryset.order_by("-created_at")

    def retrieve(self, request, *args, **kwargs) -> Any:  # type: ignore
        """Retrieve article and log read event."""
        article = self.get_object()

        if request.user.is_authenticated:
            # Log article read event
            activity_service = get_activity_service()
            activity_service.log_article_read(
                user=request.user, article_id=str(article.id)
            )

        serializer = self.get_serializer(article)
        return Response(serializer.data)

    def get_serializer_class(self) -> Any:
        """Return appropriate serializer."""
        if self.action == "retrieve":
            return ArticleDetailSerializer
        return ArticleListSerializer

    def destroy(self, request, *args, **kwargs) -> Any:
        """Delete an article created by the user."""
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required to delete an article."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        article = self.get_object()

        # Ensure user can only delete their own private articles
        if article.created_by != request.user:
            return Response(
                {"error": "You do not have permission to delete this article."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Clean up decoupled dependencies from the userstate engine
        from engines.userstate.models import Bookmark, ReadingProgress

        Bookmark.objects.filter(content_type="article", content_id=article.id).delete()
        ReadingProgress.objects.filter(article_id=article.id).delete()

        article.delete()
        logger.info(
            "article_deleted", user_id=request.user.id, article_id=str(article.id)
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="jobs/(?P<job_id>[^/.]+)/status")
    def job_status(self, request, job_id=None):
        """Get status of an article generation job."""
        job = get_object_or_404(ArticleGenerationJob, id=job_id)
        serializer = ArticleGenerationJobSerializer(job)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["post"],
        url_path="generate",
        permission_classes=[AllowAny],
    )
    def generate(self, request) -> Any:
        """
        Generate article (Background Processing).
        """
        from typing import cast

        from engines.auth.models import User

        user_id = cast(User, request.user).id if request.user.is_authenticated else None

        serializer = ArticleGenerationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        topic_id = str(serializer.validated_data["topic_id"])
        include_ca = serializer.validated_data["include_ca"]

        from engines.knowledge.models import Topic

        if not Topic.objects.filter(id=topic_id).exists():
            return Response(
                {"error": "Topic not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Create Job
        job = ArticleGenerationJob.objects.create(
            topic_id=topic_id,
            requested_by_id=user_id,
            generation_params={"include_ca": include_ca},
            status="pending",
        )

        # Submit to executor
        article_executor.submit(
            _background_article_generation, str(job.id), topic_id, include_ca, user_id
        )

        return Response(
            {
                "message": "Article generation started",
                "job_id": str(job.id),
                "status_url": f"/api/v1/articles/jobs/{job.id}/status/",
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["get"], url_path="sources")
    def sources(self, request, id=None) -> Any:  # type: ignore
        """
        Get source chunks for an article.

        GET /api/v1/articles/:id/sources/
        """
        article = self.get_object()

        source_maps = article.source_chunks.select_related(
            "chunk", "chunk__document"
        ).order_by("sequence_order")

        serializer = ArticleSourceMapSerializer(source_maps, many=True)

        return Response(
            {
                "article_id": str(article.id),
                "article_title": article.title,
                "total_sources": source_maps.count(),
                "sources": serializer.data,
            }
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="my-notebook",
        permission_classes=[IsAuthenticated],
    )
    def my_notebook(self, request) -> Any:  # type: ignore
        """
        Get user's private articles ("My Notebook").

        GET /api/v1/articles/my-notebook/
        """
        articles = (
            Article.objects.filter(created_by=request.user, is_public=False)
            .select_related("topic")
            .order_by("-created_at")
        )

        paginator = StandardLimitOffsetPagination()
        paginated_articles = paginator.paginate_queryset(articles, request)
        serializer = ArticleListSerializer(paginated_articles, many=True)
        return paginator.get_paginated_response(serializer.data)


class ArticleGenerationJobViewSet(viewsets.ReadOnlyModelViewSet):  # type: ignore
    """
    ViewSet for ArticleGenerationJobs.

    - List: GET /api/v1/articles/jobs/
    - Detail: GET /api/v1/articles/jobs/:id/
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ArticleGenerationJobSerializer
    lookup_field = "id"

    ordering_fields = ["status", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self) -> Any:
        """Get jobs for current user (or all for staff)."""
        queryset = ArticleGenerationJob.objects.select_related("topic", "article").all()

        # Filter by user for non-staff
        from typing import cast

        from engines.auth.models import User

        if not getattr(self.request.user, "is_staff", False):
            queryset = queryset.filter(requested_by=cast(User, self.request.user))

        # Filter by status
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset


# === Function Based Views (Direct Access) ===


@api_view(["GET"])
@permission_classes([AllowAny])
def list_articles(request) -> Any:  # type: ignore
    """
    List articles.

    - Anonymous users: see only public articles
    - Logged-in users: see public + own private articles
    """
    queryset = Article.objects.filter(is_published=True)

    # ===== VISIBILITY FILTERING =====
    visibility_service = get_visibility_service()
    queryset = visibility_service.filter_articles(queryset, request.user)
    # ===== END FILTERING =====

    # Apply other filters
    topic_id = request.query_params.get("topic_id")
    if topic_id:
        queryset = queryset.filter(topic_id=topic_id)

    articles = (
        queryset.select_related("topic", "created_by")
        .defer("content")
        .order_by("-created_at")
    )

    paginator = StandardLimitOffsetPagination()
    paginated_articles = paginator.paginate_queryset(articles, request)
    serializer = ArticleListSerializer(paginated_articles, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_notebook(request) -> Any:  # type: ignore
    """
    Get user's private articles ("My Notebook").

    GET /api/v1/articles/my-notebook/
    """
    articles = (
        Article.objects.filter(created_by=request.user, is_public=False)
        .select_related("topic", "created_by")
        .defer("content")
        .order_by("-created_at")
    )

    paginator = StandardLimitOffsetPagination()
    paginated_articles = paginator.paginate_queryset(articles, request)
    serializer = ArticleListSerializer(paginated_articles, many=True)
    return paginator.get_paginated_response(serializer.data)
