"""
Knowledge Engine URLs
"""

from django.urls import include, path

from rest_framework.routers import DefaultRouter

from engines.knowledge.views import (
    ChunkTopicMapViewSet,
    HierarchyListView,
    ModuleViewSet,
    ProgramViewSet,
    SearchViewSet,
    SubjectViewSet,
    ThemeViewSet,
    TopicViewSet,
)

router = DefaultRouter()
router.register(r"programs", ProgramViewSet, basename="program")
router.register(r"subjects", SubjectViewSet, basename="subject")
router.register(r"modules", ModuleViewSet, basename="module")
router.register(r"topics", TopicViewSet, basename="topic")
router.register(r"mappings", ChunkTopicMapViewSet, basename="mapping")
router.register(r"themes", ThemeViewSet, basename="theme")
router.register(r"search", SearchViewSet, basename="search")

urlpatterns = [
    path("hierarchy/", HierarchyListView.as_view(), name="hierarchy"),
    path("", include(router.urls)),
]
