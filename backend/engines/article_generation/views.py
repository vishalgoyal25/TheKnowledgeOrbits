"""
Article Generation Engine Views
"""

import structlog
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404

from .models import Article, ArticleGenerationJob
from .serializers import (
    ArticleListSerializer,
    ArticleDetailSerializer,
    ArticleGenerationRequestSerializer,
    ArticleGenerationJobSerializer,
    ArticleSourceMapSerializer,
)
from .services.generation_service import ArticleGenerationService

logger = structlog.get_logger(__name__)


class ArticleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Articles.
    
    - List: GET /api/v1/articles/
    - Detail: GET /api/v1/articles/:id/
    - Generate: POST /api/v1/articles/generate/
    - Sources: GET /api/v1/articles/:id/sources/
    """
    
    permission_classes = [AllowAny]
    lookup_field = 'id'
    
    ordering_fields = ['created_at', 'title', 'review_status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get articles (published only for non-staff)."""
        queryset = Article.objects.select_related('topic', 'topic__subject').all()
        
        # Filter by published status for non-staff
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_published=True)
        
        # Filter by topic
        topic_id = self.request.query_params.get('topic_id')
        if topic_id:
            queryset = queryset.filter(topic_id=topic_id)
        
        # Filter by review status
        review_status = self.request.query_params.get('review_status')
        if review_status:
            queryset = queryset.filter(review_status=review_status)
        
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer."""
        if self.action == 'retrieve':
            return ArticleDetailSerializer
        return ArticleListSerializer
    
    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
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
        
        topic_id = str(serializer.validated_data['topic_id'])
        include_ca = serializer.validated_data['include_ca']
        
        try:
            # Generate article
            result = ArticleGenerationService.generate_article(
                topic_id=topic_id,
                include_ca=include_ca,
                user_id=request.user.id
            )
            
            # Fetch generated article
            article = Article.objects.get(id=result['article_id'])
            
            return Response(
                {
                    'message': 'Article generated successfully',
                    'article': ArticleDetailSerializer(article).data,
                    'metadata': {
                        'word_count': result['word_count'],
                        'quality_score': result['quality_score'],
                        'source_chunks': result['source_chunks'],
                    }
                },
                status=status.HTTP_201_CREATED
            )
        
        except ValueError as e:
            logger.warning("article_generation_validation_error", error=str(e))
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        except Exception as e:
            logger.error("article_generation_error", error=str(e))
            return Response(
                {'error': 'Article generation failed. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'], url_path='sources')
    def sources(self, request, id=None):
        """
        Get source chunks for an article.
        
        GET /api/v1/articles/:id/sources/
        """
        article = self.get_object()
        
        source_maps = article.source_chunks.select_related(
            'chunk',
            'chunk__document'
        ).order_by('sequence_order')
        
        serializer = ArticleSourceMapSerializer(source_maps, many=True)
        
        return Response({
            'article_id': str(article.id),
            'article_title': article.title,
            'total_sources': source_maps.count(),
            'sources': serializer.data
        })


class ArticleGenerationJobViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for ArticleGenerationJobs.
    
    - List: GET /api/v1/articles/jobs/
    - Detail: GET /api/v1/articles/jobs/:id/
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = ArticleGenerationJobSerializer
    lookup_field = 'id'
    
    ordering_fields = ['status', 'created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get jobs for current user (or all for staff)."""
        queryset = ArticleGenerationJob.objects.select_related(
            'topic',
            'article'
        ).all()
        
        # Filter by user for non-staff
        if not self.request.user.is_staff:
            queryset = queryset.filter(requested_by=self.request.user)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset

        