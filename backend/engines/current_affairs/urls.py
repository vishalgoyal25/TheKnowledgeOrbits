"""
Current Affairs Engine - URLs
"""

from django.urls import include, path

from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"sources", views.CASourceViewSet, basename="ca-source")
router.register(r"articles", views.CAArticleViewSet, basename="ca-article")
router.register(r"chunks", views.CAChunkViewSet, basename="ca-chunk")
router.register(r"links", views.CATopicLinkViewSet, basename="ca-link")

urlpatterns = [
    path("", include(router.urls)),
]
