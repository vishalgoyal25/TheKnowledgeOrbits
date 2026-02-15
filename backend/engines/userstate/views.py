"""
User State Engine Views

8 Endpoints:
1. GET /progress/
2. GET /mastery/
3. GET /events/
4. GET /bookmarks/
5. POST /bookmarks/
6. DELETE /bookmarks/{id}/
7. GET /reading-progress/{article_id}/
8. PUT /reading-progress/{article_id}/
"""

import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from engines.userstate.models import Bookmark, ReadingProgress
from engines.userstate.serializers import (
    UserProgressSerializer, TopicMasterySerializer, UserEventSerializer,
    BookmarkSerializer, BookmarkCreateSerializer,
    ReadingProgressSerializer, ReadingProgressUpdateSerializer
)
from engines.userstate.services.bookmark_service import get_bookmark_service
from engines.userstate.services.progress_service import get_progress_service

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_progress(request):
    """
    Get user progress.
    
    GET /api/v1/userstate/progress/
    """
    progress_service = get_progress_service()
    progress = progress_service.update_progress(request.user)
    
    serializer = UserProgressSerializer(progress)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_mastery(request):
    """
    Get topic mastery scores.
    
    GET /api/v1/userstate/mastery/
    Query params:
        - weak (bool): Filter weak topics
        - strong (bool): Filter strong topics
    """
    masteries = request.user.topic_masteries.select_related('topic').all()
    
    # Apply filters
    if request.query_params.get('weak'):
        masteries = masteries.filter(mastery_score__lt=50, questions_attempted__gte=3)
    
    if request.query_params.get('strong'):
        masteries = masteries.filter(mastery_score__gte=80, questions_attempted__gte=5)
    
    masteries = masteries.order_by('-mastery_score')
    
    serializer = TopicMasterySerializer(masteries, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_events(request):
    """
    Get recent user events.
    
    GET /api/v1/userstate/events/
    Query params:
        - limit (int): Number of events (default 20)
        - event_type (str): Filter by type
    """
    limit = int(request.query_params.get('limit', 20))
    event_type = request.query_params.get('event_type')
    
    events = request.user.events.all()
    
    if event_type:
        events = events.filter(event_type=event_type)
    
    events = events[:limit]
    
    serializer = UserEventSerializer(events, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_bookmarks(request):
    """
    List user bookmarks.
    
    GET /api/v1/userstate/bookmarks/
    Query params:
        - content_type (str): Filter by type
    """
    content_type = request.query_params.get('content_type')
    
    bookmark_service = get_bookmark_service()
    
    try:
        bookmarks = bookmark_service.get_bookmarks(
            user=request.user,
            content_type=content_type
        )
        
        serializer = BookmarkSerializer(bookmarks, many=True)
        return Response(serializer.data)
        
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_bookmark(request):
    """
    Add bookmark.
    
    POST /api/v1/userstate/bookmarks/
    Body: {
        "content_type": "article",
        "content_id": "uuid",
        "notes": "optional"
    }
    """
    serializer = BookmarkCreateSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    bookmark_service = get_bookmark_service()
    
    try:
        bookmark = bookmark_service.add_bookmark(
            user=request.user,
            content_type=serializer.validated_data['content_type'],
            content_id=str(serializer.validated_data['content_id']),
            notes=serializer.validated_data.get('notes', '')
        )
        
        result = BookmarkSerializer(bookmark)
        return Response(result.data, status=status.HTTP_201_CREATED)
        
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_bookmark(request, bookmark_id):
    """
    Remove bookmark.
    
    DELETE /api/v1/userstate/bookmarks/{bookmark_id}/
    """
    bookmark_service = get_bookmark_service()
    
    try:
        bookmark_service.remove_bookmark(
            user=request.user,
            bookmark_id=bookmark_id
        )
        
        return Response({'message': 'Bookmark removed'})
        
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_reading_progress(request, article_id):
    """
    Get reading progress for article.
    
    GET /api/v1/userstate/reading-progress/{article_id}/
    """
    try:
        progress = ReadingProgress.objects.get(
            user=request.user,
            article_id=article_id
        )
        serializer = ReadingProgressSerializer(progress)
        return Response(serializer.data)
        
    except ReadingProgress.DoesNotExist:
        return Response(
            {'percent_read': 0, 'last_position': 0},
            status=status.HTTP_200_OK
        )


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_reading_progress(request, article_id):
    """
    Update reading progress.
    
    PUT /api/v1/userstate/reading-progress/{article_id}/
    Body: {
        "percent_read": 45.5,
        "last_position": 1234
    }
    """
    serializer = ReadingProgressUpdateSerializer(data={
        **request.data,
        'article_id': article_id
    })
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    progress, created = ReadingProgress.objects.update_or_create(
        user=request.user,
        article_id=article_id,
        defaults={
            'percent_read': serializer.validated_data['percent_read'],
            'last_position': serializer.validated_data['last_position']
        }
    )
    
    result = ReadingProgressSerializer(progress)
    return Response(result.data)

    