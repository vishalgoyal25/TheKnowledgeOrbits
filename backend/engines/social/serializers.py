"""
engines/social/serializers.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Social Interaction Engine — DRF Serializers (Phase D).

  SocialCountSerializer   — GET counts + user_liked flag
  LikeToggleSerializer    — POST toggle input (content_type + content_id)
  CommentSerializer       — read — nested replies, soft-delete masking
  CommentCreateSerializer — write — validates body, parent scoping, nesting limit
  ShareCreateSerializer   — POST share log input
"""

from rest_framework import serializers

from engines.social.models import (
    CONTENT_TYPE_CHOICES,
    PLATFORM_CHOICES,
    Comment,
    Like,
    SocialCount,
)

# ── SocialCountSerializer ─────────────────────────────────────────────────────


class SocialCountSerializer(serializers.ModelSerializer):
    """
    Serialises one SocialCount row.
    Injects `user_liked` from the request context — True if the authenticated
    user has a Like record for this (content_type, content_id), False otherwise.
    Always False for anonymous requests.
    """

    user_liked = serializers.SerializerMethodField()

    class Meta:
        model = SocialCount
        fields = [
            "content_type",
            "content_id",
            "like_count",
            "comment_count",
            "share_count",
            "user_liked",
        ]

    def get_user_liked(self, obj: SocialCount) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return Like.objects.filter(
            user=request.user,
            content_type=obj.content_type,
            content_id=obj.content_id,
        ).exists()


# ── LikeToggleSerializer ──────────────────────────────────────────────────────


class LikeToggleSerializer(serializers.Serializer):
    """Input-only serializer for the like-toggle endpoint."""

    content_type = serializers.ChoiceField(choices=CONTENT_TYPE_CHOICES)
    content_id = serializers.UUIDField()


# ── CommentSerializer ─────────────────────────────────────────────────────────


class CommentSerializer(serializers.ModelSerializer):
    """
    Read serializer for one comment.

    Soft-delete masking:
      is_deleted=True  →  body becomes "[deleted]", user_display_name becomes "[deleted]"

    Replies:
      Top-level comments (parent=None) include up to 10 direct child comments.
      Reply-level comments always return replies=[] to prevent infinite nesting.
    """

    user_display_name = serializers.SerializerMethodField()
    user_avatar_url = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()
    parent_id = serializers.UUIDField(source="parent.id", read_only=True, default=None)

    class Meta:
        model = Comment
        fields = [
            "id",
            "user_id",
            "user_display_name",
            "user_avatar_url",
            "body",
            "parent_id",
            "replies",
            "created_at",
            "edited_at",
            "is_deleted",
        ]

    def get_user_display_name(self, obj: Comment) -> str:
        if obj.is_deleted:
            return "[deleted]"
        return obj.user.full_name or obj.user.email

    def get_user_avatar_url(self, obj: Comment) -> str:
        if obj.is_deleted:
            return ""
        try:
            return obj.user.profile.avatar_url or ""
        except Exception:
            return ""

    def get_body(self, obj: Comment) -> str:
        if obj.is_deleted:
            return "[deleted]"
        return obj.body

    def get_replies(self, obj: Comment) -> list:
        # Replies themselves never expose their own replies (1-level max)
        if obj.parent_id is not None:
            return []
        child_qs = obj.replies.select_related("user").order_by("created_at")[:10]
        return list(CommentSerializer(child_qs, many=True, context=self.context).data)


# ── CommentCreateSerializer ───────────────────────────────────────────────────


class CommentCreateSerializer(serializers.Serializer):
    """
    Write serializer for creating a comment or reply.

    Validations:
      - body: not blank, max 1000 chars
      - parent_id (optional): must exist, belong to same (content_type, content_id),
        be a top-level comment (no 2nd-level nesting), and not be soft-deleted
    """

    content_type = serializers.ChoiceField(choices=CONTENT_TYPE_CHOICES)
    content_id = serializers.UUIDField()
    body = serializers.CharField(
        max_length=1000,
        allow_blank=False,
        trim_whitespace=True,
    )
    parent_id = serializers.UUIDField(required=False, allow_null=True, default=None)

    def validate(self, data: dict) -> dict:
        parent_id = data.get("parent_id")
        if not parent_id:
            return data

        try:
            parent = Comment.objects.get(pk=parent_id)
        except Comment.DoesNotExist:
            raise serializers.ValidationError(
                {"parent_id": "Parent comment not found."}
            )

        if parent.content_type != data["content_type"] or str(parent.content_id) != str(
            data["content_id"]
        ):
            raise serializers.ValidationError(
                {"parent_id": "Parent comment belongs to different content."}
            )

        if parent.parent_id is not None:
            raise serializers.ValidationError(
                {"parent_id": "Cannot reply to a reply — max 1 level of nesting."}
            )

        if parent.is_deleted:
            raise serializers.ValidationError(
                {"parent_id": "Cannot reply to a deleted comment."}
            )

        # Attach resolved parent object so the view doesn't re-query
        data["parent"] = parent
        return data


# ── ShareCreateSerializer ─────────────────────────────────────────────────────


class ShareCreateSerializer(serializers.Serializer):
    """Input-only serializer for logging a share action."""

    content_type = serializers.ChoiceField(choices=CONTENT_TYPE_CHOICES)
    content_id = serializers.UUIDField()
    platform = serializers.ChoiceField(
        choices=PLATFORM_CHOICES,
        default="copy_link",
    )
