"""
engines/social/urls.py
━━━━━━━━━━━━━━━━━━━━━━
Social Interaction Engine — URL Routing (Phase D).

All routes are under /api/v1/social/ (registered in core/urls.py).

  GET    counts/                  → SocialCountView       (public)
  POST   likes/toggle/            → LikeToggleView        (auth required)
  GET    comments/                → CommentListView       (public)
  POST   comments/create/         → CommentCreateView     (auth required)
  PATCH  comments/<uuid>/         → CommentUpdateDestroyView (auth + owner)
  DELETE comments/<uuid>/         → CommentUpdateDestroyView (auth + owner)
  POST   shares/                  → ShareCreateView       (auth required)
"""

from django.urls import path

from engines.social.views import (
    CommentCreateView,
    CommentListView,
    CommentUpdateDestroyView,
    LikeToggleView,
    ShareCreateView,
    SocialCountView,
)

urlpatterns = [
    path("counts/", SocialCountView.as_view(), name="social-counts"),
    path("likes/toggle/", LikeToggleView.as_view(), name="social-like-toggle"),
    path("comments/", CommentListView.as_view(), name="social-comment-list"),
    path("comments/create/", CommentCreateView.as_view(), name="social-comment-create"),
    path(
        "comments/<uuid:pk>/",
        CommentUpdateDestroyView.as_view(),
        name="social-comment-detail",
    ),
    path("shares/", ShareCreateView.as_view(), name="social-share-create"),
]
