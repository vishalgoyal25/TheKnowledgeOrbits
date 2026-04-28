"""
engines/social/models.py
━━━━━━━━━━━━━━━━━━━━━━━━
Social Interaction Engine — Models.

Four tables:
  Like        — one record per (user, content_type, content_id) — unique
  Comment     — threaded comments, 1 level deep (parent → child)
  Share       — audit log of share actions per platform
  SocialCount — denormalised counter cache; updated atomically via signals (Phase C)
                Never query COUNT(*) at runtime — always read from this table.

Content types (no FK enforcement — loose UUID coupling, same pattern as userstate.Bookmark):
  "daily_ca_article"  → daily_ca.DailyCaArticle
  "book_article"      → book_content.BookContent
  "quiz"              → assessment.Quiz
"""

import uuid

from django.conf import settings
from django.db import models

# ── Choices ───────────────────────────────────────────────────────────────────

CONTENT_TYPE_CHOICES = [
    ("daily_ca_article", "Daily CA Article"),
    ("book_article", "Book / Static Article"),
    ("quiz", "Quiz"),
]

PLATFORM_CHOICES = [
    ("copy_link", "Copy Link"),
    ("whatsapp", "WhatsApp"),
    ("twitter", "Twitter / X"),
    ("telegram", "Telegram"),
    ("other", "Other"),
]

# ── MODEL: Like ───────────────────────────────────────────────────────────────


class Like(models.Model):
    """
    One like per (user, content_type, content_id).
    unique_together enforces the one-like-per-user rule at the DB level.
    Signals in Phase C increment/decrement SocialCount.like_count atomically.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    content_type = models.CharField(
        max_length=50,
        choices=CONTENT_TYPE_CHOICES,
        db_index=True,
    )
    content_id = models.UUIDField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "social_like"
        unique_together = [["user", "content_type", "content_id"]]
        indexes = [
            models.Index(fields=["content_type", "content_id"]),
            models.Index(fields=["user", "content_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} liked {self.content_type}:{self.content_id}"


# ── MODEL: Comment ────────────────────────────────────────────────────────────


class Comment(models.Model):
    """
    User comment on any content type.

    Threading: max 1 level deep (parent → replies).
    parent is nullable — top-level comments have parent=None.
    Replies always have parent set; their parent.parent must be None
    (enforced in CommentCreateSerializer, Phase D).

    Soft-delete: is_deleted=True clears body and hides user — thread structure preserved.
    Moderation: is_flagged=True sends comment to admin mod queue (Phase E).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    content_type = models.CharField(
        max_length=50,
        choices=CONTENT_TYPE_CHOICES,
        db_index=True,
    )
    content_id = models.UUIDField(db_index=True)
    body = models.TextField(max_length=1000)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replies",
    )
    is_deleted = models.BooleanField(default=False, db_index=True)
    is_flagged = models.BooleanField(default=False, db_index=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "social_comment"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["content_type", "content_id", "created_at"]),
            models.Index(fields=["parent"]),
            models.Index(fields=["user"]),
            models.Index(fields=["is_deleted", "is_flagged"]),
        ]

    def __str__(self) -> str:
        preview = self.body[:40] if not self.is_deleted else "[deleted]"
        return f"{self.user_id} on {self.content_type}:{self.content_id} — {preview}"


# ── MODEL: Share ──────────────────────────────────────────────────────────────


class Share(models.Model):
    """
    Audit record of a share action.
    One row per share event — not unique per user (users can share multiple times).
    Signals in Phase C increment SocialCount.share_count.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shares",
    )
    content_type = models.CharField(
        max_length=50,
        choices=CONTENT_TYPE_CHOICES,
        db_index=True,
    )
    content_id = models.UUIDField(db_index=True)
    platform = models.CharField(
        max_length=20,
        choices=PLATFORM_CHOICES,
        default="copy_link",
    )
    shared_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "social_share"
        indexes = [
            models.Index(fields=["content_type", "content_id"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} shared {self.content_type}:{self.content_id} via {self.platform}"


# ── MODEL: SocialCount ────────────────────────────────────────────────────────


class SocialCount(models.Model):
    """
    Denormalised counter cache — one row per (content_type, content_id).

    NEVER updated manually. Only written by Phase C signals using F() expressions:
        SocialCount.objects.filter(...).update(like_count=F("like_count") + 1)

    Always read from this table at runtime — never COUNT(*) on Like/Comment/Share.
    Initialised lazily on first like/comment/share via get_or_create in signals.
    """

    content_type = models.CharField(
        max_length=50,
        choices=CONTENT_TYPE_CHOICES,
    )
    content_id = models.UUIDField()
    like_count = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "social_count"
        unique_together = [["content_type", "content_id"]]
        indexes = [
            models.Index(fields=["content_type", "content_id"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.content_type}:{self.content_id} "
            f"❤️{self.like_count} 💬{self.comment_count} 📤{self.share_count}"
        )
