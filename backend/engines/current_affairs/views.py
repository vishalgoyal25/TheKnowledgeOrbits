"""
Current Affairs Engine - Views
"""

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django.utils import timezone
from datetime import timedelta

from .models import CASource, CAArticle, CAChunk, CATopicLink
from .serializers import (
    CASourceSerializer,
    CAArticleSerializer,
    CAChunkSerializer,
    CATopicLinkSerializer,
)
from .services.rss_scraper import RSSScraperService
from .services.ca_processor import CAProcessorService
from .services.topic_linker import TopicLinkerService


class CASourceViewSet(viewsets.ModelViewSet):
    """CA Source management"""

    queryset = CASource.objects.all()
    serializer_class = CASourceSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["name", "last_scraped_at", "article_count"]
    ordering = ["name"]

    def get_permissions(self):
        # Only admins can create/update/delete sources
        if self.action in ["create", "update", "partial_update", "destroy", "scrape"]:
            return [IsAdminUser()]
        return [AllowAny()]

    @action(detail=True, methods=["post"])
    def scrape(self, request, pk=None):
        """Manually trigger scraping for a source"""
        source = self.get_object()
        result = RSSScraperService.scrape_source(source)

        return Response(
            {
                "message": f"Scraped {result['articles_new']} new articles",
                "result": result,
            }
        )


class CAArticleViewSet(viewsets.ReadOnlyModelViewSet):
    """CA Article viewing"""

    queryset = CAArticle.objects.all()
    serializer_class = CAArticleSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["title", "content", "author"]
    ordering_fields = ["published_at", "word_count", "chunk_count"]
    ordering = ["-published_at"]

    def get_queryset(self):
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


class CAChunkViewSet(viewsets.ReadOnlyModelViewSet):
    """CA Chunk viewing"""

    queryset = CAChunk.objects.all()
    serializer_class = CAChunkSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["published_at", "confidence_score"]
    ordering = ["-published_at"]

    def get_queryset(self):
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
    def recent(self, request):
        """Get recent CA chunks (last 30 days)"""
        thirty_days_ago = timezone.now() - timedelta(days=30)

        chunks = self.get_queryset().filter(
            published_at__gte=thirty_days_ago, is_expired=False
        )[:20]

        serializer = self.get_serializer(chunks, many=True)
        return Response(serializer.data)


class CATopicLinkViewSet(viewsets.ReadOnlyModelViewSet):
    """CA Topic Link viewing"""

    queryset = CATopicLink.objects.all()
    serializer_class = CATopicLinkSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["relevance_score", "created_at"]
    ordering = ["-relevance_score"]

    def get_queryset(self):
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
