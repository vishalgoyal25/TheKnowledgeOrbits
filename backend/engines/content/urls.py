"""
Content Engine URLs
"""

from django.urls import include, path

from rest_framework.routers import DefaultRouter

from engines.content.views import (
    AssetViewSet,
    ChunkViewSet,
    DocumentViewSet,
    EmbeddingViewSet,
    IngestionJobViewSet,
)

router = DefaultRouter()
router.register(r"documents", DocumentViewSet, basename="document")
router.register(r"chunks", ChunkViewSet, basename="chunk")
router.register(r"embeddings", EmbeddingViewSet, basename="embedding")
router.register(r"assets", AssetViewSet, basename="asset")
router.register(r"jobs", IngestionJobViewSet, basename="ingestion-job")

urlpatterns = [
    path("", include(router.urls)),
]
