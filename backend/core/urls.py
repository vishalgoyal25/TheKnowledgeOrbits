"""
URL configuration for TheKnowledgeOrbits.
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint."""
    return Response({
        'status': 'healthy',
        'message': 'TheKnowledgeOrbits API is running'
    }, status=status.HTTP_200_OK)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/health/', health_check, name='health-check'),
    
    # Engine URLs will be added here as we build them

    # Content Engine
    path('api/v1/content/', include('engines.content.urls')),
    
    # Knowledge Engine
    path('api/v1/knowledge/', include('engines.knowledge.urls')),

    # Article Generation Engine
    path('api/v1/articles/', include('engines.article_generation.urls')),

    # Current Affairs Engine
    path('api/v1/ca/', include('engines.current_affairs.urls')),

    # Assessment Engine
    # path('api/v1/assessment/', include('engines.assessment.urls')),
    
    # User State Engine
    # path('api/v1/user-state/', include('engines.userstate.urls')),
    
    # Analytics Engine
    # path('api/v1/analytics/', include('engines.analytics.urls')),
    
    # Auth Engine
    # path('api/v1/auth/', include('engines.auth.urls')),
]
