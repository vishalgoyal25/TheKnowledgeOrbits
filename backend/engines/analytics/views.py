"""
Analytics Engine Views

Dashboard API Endpoints:
1. GET /dashboard/
2. GET /weekly-stats/
3. GET /monthly-stats/
4. GET /insights/
5. POST /generate-insights/
"""

import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.cache import cache

from engines.analytics.services.dashboard_service import get_dashboard_service
from engines.analytics.services.analytics_service import get_analytics_service
from engines.analytics.services.insights_service import get_insights_service
from engines.analytics.serializers import InsightSerializer

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_dashboard(request):
    """
    Get complete dashboard overview.

    GET /api/v1/analytics/dashboard/

    Returns:
    - Overview stats (articles, quizzes, streak)
    - Weekly performance
    - Topic mastery (weak & strong)
    - Recent activity
    - Active insights
    """
    # Check cache first
    cache_key = f"dashboard_{request.user.id}"
    cached_data = cache.get(cache_key)

    if cached_data:
        logger.debug(f"Dashboard cache hit: {request.user.email}")
        return Response(cached_data)

    # Generate dashboard
    dashboard_service = get_dashboard_service()
    data = dashboard_service.get_dashboard_overview(request.user)

    # Cache for 5 minutes
    cache.set(cache_key, data, 300)

    logger.info(f"Dashboard generated: {request.user.email}")

    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_weekly_stats(request):
    """
    Get weekly statistics.

    GET /api/v1/analytics/weekly-stats/
    """
    analytics_service = get_analytics_service()
    stats = analytics_service.get_weekly_stats(request.user)

    return Response(stats)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_monthly_stats(request):
    """
    Get monthly statistics.

    GET /api/v1/analytics/monthly-stats/
    """
    analytics_service = get_analytics_service()
    stats = analytics_service.get_monthly_stats(request.user)

    return Response(stats)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_insights(request):
    """
    Get active insights.

    GET /api/v1/analytics/insights/
    """
    insights_service = get_insights_service()
    insights = insights_service.get_active_insights(request.user)

    serializer = InsightSerializer(insights, many=True)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def generate_insights(request):
    """
    Generate new insights for user.

    POST /api/v1/analytics/generate-insights/
    """
    insights_service = get_insights_service()
    insights = insights_service.generate_insights(request.user)

    # Invalidate dashboard cache
    cache_key = f"dashboard_{request.user.id}"
    cache.delete(cache_key)

    serializer = InsightSerializer(insights, many=True)
    return Response(serializer.data, status=status.HTTP_201_CREATED)
