"""
Knowledge Engine URLs
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from engines.knowledge.views import (
    ProgramViewSet,
    SubjectViewSet,
    ModuleViewSet,
    TopicViewSet,
    ChunkTopicMapViewSet,
    ThemeViewSet,
)

router = DefaultRouter()
router.register(r'programs', ProgramViewSet, basename='program')
router.register(r'subjects', SubjectViewSet, basename='subject')
router.register(r'modules', ModuleViewSet, basename='module')
router.register(r'topics', TopicViewSet, basename='topic')
router.register(r'mappings', ChunkTopicMapViewSet, basename='mapping')
router.register(r'themes', ThemeViewSet, basename='theme')

urlpatterns = [
    path('', include(router.urls)),
]
