"""
engines/social/views.py
━━━━━━━━━━━━━━━━━━━━━━━
Social Interaction Engine — DRF Views (Phase D).

  SocialCountView           GET  /api/v1/social/counts/
  LikeToggleView            POST /api/v1/social/likes/toggle/
  CommentListView           GET  /api/v1/social/comments/
  CommentCreateView         POST /api/v1/social/comments/create/
  CommentUpdateDestroyView  PATCH/DELETE /api/v1/social/comments/<uuid>/
  ShareCreateView           POST /api/v1/social/shares/

Auth rules:
  Read  (counts, comment list) → AllowAny — public, no token required
  Write (like, comment, share) → IsAuthenticated — JWT required
"""

import structlog
from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from engines.social.models import Comment, Like, Share, SocialCount
from engines.social.serializers import (
    CommentCreateSerializer,
    CommentSerializer,
    LikeToggleSerializer,
    ShareCreateSerializer,
    SocialCountSerializer,
)

logger = structlog.get_logger(__name__)

# ── Pagination ────────────────────────────────────────────────────────────────


class CommentPagination(PageNumberPagination):
    """20 top-level comments per page; clients may request up to 50."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


# ── SocialCountView ───────────────────────────────────────────────────────────


class SocialCountView(APIView):
    """
    GET /api/v1/social/counts/?content_type=<str>&content_id=<uuid>

    Returns like/comment/share counts for any content item.
    Also returns user_liked=True/False when an auth token is present.
    Returns all-zero counts (and creates no DB row) when no activity exists yet.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        content_type = request.query_params.get("content_type", "").strip()
        content_id = request.query_params.get("content_id", "").strip()

        if not content_type or not content_id:
            return Response(
                {"detail": "content_type and content_id query params are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        count_obj = SocialCount.objects.filter(
            content_type=content_type,
            content_id=content_id,
        ).first()

        if count_obj is None:
            # Return zero counts without creating a DB row
            return Response(
                {
                    "content_type": content_type,
                    "content_id": content_id,
                    "like_count": 0,
                    "comment_count": 0,
                    "share_count": 0,
                    "user_liked": False,
                }
            )

        serializer = SocialCountSerializer(count_obj, context={"request": request})
        return Response(serializer.data)


# ── LikeToggleView ────────────────────────────────────────────────────────────


class LikeToggleView(APIView):
    """
    POST /api/v1/social/likes/toggle/
    Body: { content_type, content_id }

    Idempotent toggle:
      Like exists  → delete it (unlike)  → returns { liked: false, like_count: N }
      Like missing → create it (like)    → returns { liked: true,  like_count: N }

    SocialCount is updated atomically by the post_save / post_delete signal in Phase C.
    The refreshed count is read back from the DB after the signal fires.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LikeToggleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        content_type = serializer.validated_data["content_type"]
        content_id = serializer.validated_data["content_id"]

        existing = Like.objects.filter(
            user=request.user,
            content_type=content_type,
            content_id=content_id,
        ).first()

        if existing:
            existing.delete()  # triggers post_delete signal → like_count F()-1
            liked = False
            logger.info(
                "social_unlike",
                user_id=str(request.user.id),
                content_type=content_type,
                content_id=str(content_id),
            )
        else:
            Like.objects.create(
                user=request.user,
                content_type=content_type,
                content_id=content_id,
            )  # triggers post_save signal → like_count F()+1
            liked = True
            logger.info(
                "social_like",
                user_id=str(request.user.id),
                content_type=content_type,
                content_id=str(content_id),
            )

        # Read fresh count from cache (signal already updated it)
        count_row = SocialCount.objects.filter(
            content_type=content_type,
            content_id=content_id,
        ).first()
        like_count = count_row.like_count if count_row else 0

        return Response(
            {"liked": liked, "like_count": like_count},
            status=status.HTTP_200_OK,
        )


# ── CommentListView ───────────────────────────────────────────────────────────


class CommentListView(APIView):
    """
    GET /api/v1/social/comments/?content_type=<str>&content_id=<uuid>[&page=N]

    Returns paginated top-level comments (parent=None, is_deleted=False).
    Each comment includes up to 10 direct replies (nested, read-only).
    Ordered oldest-first for natural thread reading order.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        content_type = request.query_params.get("content_type", "").strip()
        content_id = request.query_params.get("content_id", "").strip()

        if not content_type or not content_id:
            return Response(
                {"detail": "content_type and content_id query params are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = (
            Comment.objects.filter(
                content_type=content_type,
                content_id=content_id,
                parent__isnull=True,  # top-level only
                is_deleted=False,
            )
            .select_related("user", "user__profile")
            .prefetch_related("replies__user", "replies__user__profile")
            .order_by("created_at")
        )

        paginator = CommentPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = CommentSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


# ── CommentCreateView ─────────────────────────────────────────────────────────


class CommentCreateView(APIView):
    """
    POST /api/v1/social/comments/create/
    Body: { content_type, content_id, body, parent_id? }

    Creates a top-level comment or a 1-level reply.
    SocialCount.comment_count is incremented by the post_save signal.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CommentCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        vd = serializer.validated_data
        comment = Comment.objects.create(
            user=request.user,
            content_type=vd["content_type"],
            content_id=vd["content_id"],
            body=vd["body"],
            parent=vd.get("parent"),  # None for top-level
        )

        logger.info(
            "social_comment_created",
            comment_id=str(comment.pk),
            content_type=comment.content_type,
            content_id=str(comment.content_id),
            user_id=str(request.user.id),
            is_reply=comment.parent_id is not None,
        )

        out = CommentSerializer(comment, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)


# ── CommentUpdateDestroyView ──────────────────────────────────────────────────


class CommentUpdateDestroyView(APIView):
    """
    PATCH  /api/v1/social/comments/<uuid>/  — edit own comment body
    DELETE /api/v1/social/comments/<uuid>/  — soft-delete own comment

    Owner check: request.user must match comment.user.
    PATCH  → updates body, stamps edited_at=now().
    DELETE → sets is_deleted=True, clears body. The pre_save/post_save signal
             pair detects the False→True transition and decrements comment_count.
    """

    permission_classes = [IsAuthenticated]

    def _get_owned_comment(self, pk, user):
        """Return the comment if it exists and belongs to user, else None."""
        try:
            comment = Comment.objects.get(pk=pk, is_deleted=False)
        except Comment.DoesNotExist:
            return None, Response(
                {"detail": "Comment not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if comment.user_id != user.id:
            return None, Response(
                {"detail": "You can only edit or delete your own comments."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return comment, None

    def patch(self, request, pk):
        comment, err = self._get_owned_comment(pk, request.user)
        if err:
            return err

        body = request.data.get("body", "").strip()
        if not body:
            return Response(
                {"detail": "body must not be blank."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(body) > 1000:
            return Response(
                {"detail": "body must be 1000 characters or fewer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        comment.body = body
        comment.edited_at = timezone.now()
        comment.save(update_fields=["body", "edited_at", "updated_at"])

        logger.info(
            "social_comment_edited",
            comment_id=str(pk),
            user_id=str(request.user.id),
        )

        out = CommentSerializer(comment, context={"request": request})
        return Response(out.data)

    def delete(self, request, pk):
        comment, err = self._get_owned_comment(pk, request.user)
        if err:
            return err

        comment.body = ""
        comment.is_deleted = True
        comment.save(update_fields=["body", "is_deleted", "updated_at"])
        # pre_save cached is_deleted=False; post_save detects False→True → decrements

        logger.info(
            "social_comment_soft_deleted_by_user",
            comment_id=str(pk),
            user_id=str(request.user.id),
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


# ── ShareCreateView ───────────────────────────────────────────────────────────


class ShareCreateView(APIView):
    """
    POST /api/v1/social/shares/
    Body: { content_type, content_id, platform }

    Logs one share audit record. share_count incremented by post_save signal.
    Returns fresh share_count after the signal fires.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ShareCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        vd = serializer.validated_data
        Share.objects.create(
            user=request.user,
            content_type=vd["content_type"],
            content_id=vd["content_id"],
            platform=vd.get("platform", "copy_link"),
        )

        logger.info(
            "social_share_created",
            content_type=vd["content_type"],
            content_id=str(vd["content_id"]),
            platform=vd.get("platform", "copy_link"),
            user_id=str(request.user.id),
        )

        count_row = SocialCount.objects.filter(
            content_type=vd["content_type"],
            content_id=vd["content_id"],
        ).first()
        share_count = count_row.share_count if count_row else 0

        return Response(
            {"share_count": share_count},
            status=status.HTTP_201_CREATED,
        )
