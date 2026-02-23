import sentry_sdk

"""
Current Affairs Engine - Views
"""

from datetime import timedelta
from typing import Any, Optional

from django.utils import timezone

from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

import structlog

from .models import CAArticle, CAChunk, CASource, CATopicLink
from .serializers import (
    CAArticleSerializer,
    CAChunkSerializer,
    CASourceSerializer,
    CATopicLinkSerializer,
)
from .services.rss_scraper import RSSScraperService

logger = structlog.get_logger(__name__)


class CASourceViewSet(viewsets.ModelViewSet):  # type: ignore
    """CA Source management"""

    queryset = CASource.objects.all()
    serializer_class = CASourceSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["name", "last_scraped_at", "article_count"]
    ordering = ["name"]

    def get_permissions(self) -> Any:
        # Only admins can create/update/delete sources
        if self.action in ["create", "update", "partial_update", "destroy", "scrape"]:
            return [IsAdminUser()]
        return [AllowAny()]

    @action(detail=True, methods=["post"])
    def scrape(self, request: Request, pk: Optional[str] = None) -> Response:
        """
        Manually trigger the RSS scraping and processing pipeline for a specific source.

        POST /api/v1/ca/sources/{id}/scrape/
        """
        source = self.get_object()
        logger.info(
            "manual_scrape_triggered", source_id=str(source.id), source_name=source.name
        )

        try:
            result = RSSScraperService.scrape_source(source)
            logger.info(
                "manual_scrape_completed",
                source_id=str(source.id),
                new_articles=result.get("articles_new", 0),
            )
            return Response(
                {
                    "message": f"Scraped {result['articles_new']} new articles",
                    "result": result,
                }
            )
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(
                "manual_scrape_failed",
                source_id=str(source.id),
                error=str(e),
                exc_info=True,
            )
            return Response(
                {
                    "error": "Scrape failed",
                    "message": "An error occurred during manual scraping.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CAArticleViewSet(viewsets.ReadOnlyModelViewSet):  # type: ignore
    """CA Article viewing"""

    queryset = CAArticle.objects.all()
    serializer_class = CAArticleSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["title", "content", "author"]
    ordering_fields = ["published_at", "word_count", "chunk_count"]
    ordering = ["-published_at"]

    def get_queryset(self) -> Any:
        queryset = super().get_queryset()

        # Filter by source
        source_id = self.request.query_params.get("source_id")
        if source_id:
            queryset = queryset.filter(source_id=source_id)

        # Filter by date range
        date_from = self.request.query_params.get("date_from")
        if date_from:
            queryset = queryset.filter(published_at__gte=date_from)

        date_to = self.request.query_params.get("date_to")
        if date_to:
            queryset = queryset.filter(published_at__lte=date_to)

        # Filter by processing status
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(processing_status=status_filter)

        return queryset


class CAChunkViewSet(viewsets.ReadOnlyModelViewSet):  # type: ignore
    """CA Chunk viewing"""

    queryset = CAChunk.objects.all()
    serializer_class = CAChunkSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["published_at", "confidence_score"]
    ordering = ["-published_at"]

    def get_queryset(self) -> Any:
        queryset = super().get_queryset()

        # Filter by topic
        topic_id = self.request.query_params.get("topic_id")
        if topic_id:
            queryset = queryset.filter(topic_links__topic_id=topic_id)

        # Filter by date range
        date_from = self.request.query_params.get("date_from")
        if date_from:
            queryset = queryset.filter(published_at__gte=date_from)

        date_to = self.request.query_params.get("date_to")
        if date_to:
            queryset = queryset.filter(published_at__lte=date_to)

        # Exclude expired by default
        include_expired = self.request.query_params.get("include_expired", "false")
        if include_expired.lower() != "true":
            queryset = queryset.filter(is_expired=False)

        return queryset

    @action(detail=False, methods=["get"])
    def recent(self, request: Request) -> Response:
        """
        Retrieve high-relevance CA chunks from the last 30 days.

        GET /api/v1/ca/chunks/recent/
        """
        thirty_days_ago = timezone.now() - timedelta(days=30)

        chunks = self.get_queryset().filter(
            published_at__gte=thirty_days_ago, is_expired=False
        )[:20]

        serializer = self.get_serializer(chunks, many=True)
        return Response(serializer.data)


class CATopicLinkViewSet(viewsets.ReadOnlyModelViewSet):  # type: ignore
    """CA Topic Link viewing"""

    queryset = CATopicLink.objects.all()
    serializer_class = CATopicLinkSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["relevance_score", "created_at"]
    ordering = ["-relevance_score"]

    def get_queryset(self) -> Any:
        queryset = super().get_queryset()

        # Filter by topic
        topic_id = self.request.query_params.get("topic_id")
        if topic_id:
            queryset = queryset.filter(topic_id=topic_id)

        # Filter by link method
        link_method = self.request.query_params.get("link_method")
        if link_method:
            queryset = queryset.filter(link_method=link_method)

        return queryset
