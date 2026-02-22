from typing import Any
import sentry_sdk

"""
Article Generation Engine Views
"""

import structlog
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import Article, ArticleGenerationJob
from .serializers import (
    ArticleListSerializer,
    ArticleDetailSerializer,
    ArticleGenerationRequestSerializer,
    ArticleGenerationJobSerializer,
    ArticleSourceMapSerializer,
)
from .services.generation_service import ArticleGenerationService
from engines.userstate.services.activity_service import get_activity_service

from engines.shared.services.visibility_service import get_visibility_service

logger = structlog.get_logger(__name__)


class ArticleViewSet(viewsets.ReadOnlyModelViewSet):  # type: ignore
    """
    ViewSet for Articles.

    - List: GET /api/v1/articles/
    - Detail: GET /api/v1/articles/:id/
    - Generate: POST /api/v1/articles/generate/
    - Sources: GET /api/v1/articles/:id/sources/
    """

    permission_classes = [AllowAny]
    lookup_field = "id"

    ordering_fields = ["created_at", "title", "review_status"]
    ordering = ["-created_at"]

    def get_queryset(self) -> Any:
        """Get articles (filtered by visibility)."""
        queryset = Article.objects.filter(is_published=True).select_related(
            "topic", "topic__subject"
        )

        # Apply visibility filtering (PKB Ownership Logic)
        visibility_service = get_visibility_service()
        queryset = visibility_service.filter_articles(queryset, self.request.user)  # type: ignore

        # Filter by topic
        topic_id = self.request.query_params.get("topic_id")
        if topic_id:
            queryset = queryset.filter(topic_id=topic_id)

        # Filter by review status
        review_status = self.request.query_params.get("review_status")
        if review_status:
            queryset = queryset.filter(review_status=review_status)

        return queryset

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

    @action(
        detail=False,
        methods=["post"],
        url_path="generate",
        permission_classes=[AllowAny],
    )
    def generate(self, request) -> Any:  # type: ignore
        """
        Generate article for a topic.

        POST /api/v1/articles/generate/
        Body: {
            "topic_id": "uuid",
            "include_ca": false
        }
        """
        logger.info("article_generation_requested", user_id=request.user.id)

        # Validate request
        serializer = ArticleGenerationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        topic_id = str(serializer.validated_data["topic_id"])
        include_ca = serializer.validated_data["include_ca"]

        try:
            # Generate article
            result = ArticleGenerationService.generate_article(
                topic_id=topic_id, include_ca=include_ca, user_id=request.user.id
            )

            # Fetch generated article
            article = Article.objects.get(id=result["article_id"])

            # ===== OWNERSHIP LOGIC (PKB Extension) =====
            if request.user.is_authenticated:
                # User-owned private article
                article.created_by = request.user
                article.is_public = False
                article.save()

                # Log activity
                activity_service = get_activity_service()
                activity_service.log_article_generated(
                    user=request.user, article_id=str(article.id), topic_id=topic_id
                )

                logger.info(
                    "private_article_generated",
                    user_id=request.user.id,
                    article_id=str(article.id),
                )
            else:
                # Public article for anonymous users
                article.is_public = True
                article.created_by = None
                article.save()
                logger.info(
                    "public_article_generated_anonymous", article_id=str(article.id)
                )
            # ===== END OWNERSHIP LOGIC =====

            return Response(
                {
                    "message": "Article generated successfully",
                    "article": ArticleDetailSerializer(article).data,
                    "metadata": {
                        "word_count": result["word_count"],
                        "quality_score": result["quality_score"],
                        "source_chunks": result["source_chunks"],
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        except ValueError as e:
            logger.warning("article_generation_validation_error", error=str(e))
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error("article_generation_error", error=str(e))
            return Response(
                {"error": "Article generation failed. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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

        serializer = ArticleListSerializer(articles, many=True)
        return Response(serializer.data)


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
        if not self.request.user.is_staff:
            queryset = queryset.filter(requested_by=self.request.user)  # type: ignore

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

    articles = queryset.select_related("topic").order_by("-created_at")[:20]

    serializer = ArticleListSerializer(articles, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_notebook(request) -> Any:  # type: ignore
    """
    Get user's private articles ("My Notebook").

    GET /api/v1/articles/my-notebook/
    """
    articles = (
        Article.objects.filter(created_by=request.user, is_public=False)
        .select_related("topic")
        .order_by("-created_at")
    )

    serializer = ArticleListSerializer(articles, many=True)
    return Response(serializer.data)
