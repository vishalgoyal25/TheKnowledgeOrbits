"""
engines/social/admin.py
━━━━━━━━━━━━━━━━━━━━━━━
Social Interaction Engine — Django Admin (Phase E).

Three panels:

  CommentAdmin   — primary moderation surface.
                   Filter by flagged/deleted, search by user/body,
                   bulk actions: approve (unflag), soft-delete, hard-delete.

  LikeAdmin      — audit view, read-only. Inspect who liked what.

  SocialCountAdmin — read-only counter cache inspector.
                     like_count / comment_count / share_count are never
                     editable here — only signals may write them.
"""

from django.contrib import admin

from engines.social.models import Comment, Like, Share, SocialCount


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """
    Primary moderation dashboard for user comments.

    Workflow:
      1. Filter `is_flagged=True` to see the moderation queue.
      2. Review body — use "Soft-delete selected comments" to remove without
         destroying the thread structure, or hard-delete if the row must go.
      3. Use "Unflag selected comments" to clear false-positive flags.
    """

    list_display = (
        "short_body",
        "user",
        "content_type",
        "short_content_id",
        "is_flagged",
        "is_deleted",
        "parent_id",
        "created_at",
    )
    list_filter = ("content_type", "is_flagged", "is_deleted")
    search_fields = ("user__email", "user__full_name", "body")
    ordering = ("-created_at",)
    readonly_fields = (
        "id",
        "user",
        "content_type",
        "content_id",
        "parent",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "created_at"
    list_per_page = 50

    actions = ["action_soft_delete", "action_unflag"]

    # ── Display helpers ───────────────────────────────────────────────────────

    @admin.display(description="Body")
    def short_body(self, obj: Comment) -> str:
        if obj.is_deleted:
            return "[deleted]"
        return obj.body[:80] + ("…" if len(obj.body) > 80 else "")

    @admin.display(description="Content ID")
    def short_content_id(self, obj: Comment) -> str:
        return str(obj.content_id)[:8] + "…"

    # ── Bulk actions ──────────────────────────────────────────────────────────

    @admin.action(description="Soft-delete selected comments (preserves thread)")
    def action_soft_delete(self, request, queryset):
        updated = 0
        for comment in queryset.filter(is_deleted=False):
            comment.body = ""
            comment.is_deleted = True
            comment.save(update_fields=["body", "is_deleted", "updated_at"])
            # post_save signal fires → comment_count decremented via Phase C
            updated += 1
        self.message_user(request, f"{updated} comment(s) soft-deleted.")

    @admin.action(description="Unflag selected comments (clear moderation flag)")
    def action_unflag(self, request, queryset):
        count = queryset.update(is_flagged=False)
        self.message_user(request, f"{count} comment(s) unflagged.")


# ── LikeAdmin ─────────────────────────────────────────────────────────────────


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    """
    Read-only audit view — who liked what and when.
    No moderation actions needed; likes are hidden counts, not user-visible text.
    """

    list_display = ("user", "content_type", "short_content_id", "created_at")
    list_filter = ("content_type",)
    search_fields = ("user__email", "user__full_name")
    ordering = ("-created_at",)
    readonly_fields = ("id", "user", "content_type", "content_id", "created_at")
    list_per_page = 50

    def has_add_permission(self, request) -> bool:
        return False  # Likes must come from the API only

    def has_change_permission(self, request, obj=None) -> bool:
        return False  # Immutable audit records

    @admin.display(description="Content ID")
    def short_content_id(self, obj: Like) -> str:
        return str(obj.content_id)[:8] + "…"


# ── ShareAdmin ────────────────────────────────────────────────────────────────


@admin.register(Share)
class ShareAdmin(admin.ModelAdmin):
    """
    Read-only audit log of share events per platform.
    """

    list_display = ("user", "content_type", "short_content_id", "platform", "shared_at")
    list_filter = ("content_type", "platform")
    search_fields = ("user__email", "user__full_name")
    ordering = ("-shared_at",)
    readonly_fields = (
        "id",
        "user",
        "content_type",
        "content_id",
        "platform",
        "shared_at",
    )
    list_per_page = 50

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    @admin.display(description="Content ID")
    def short_content_id(self, obj: Share) -> str:
        return str(obj.content_id)[:8] + "…"


# ── SocialCountAdmin ──────────────────────────────────────────────────────────


@admin.register(SocialCount)
class SocialCountAdmin(admin.ModelAdmin):
    """
    Read-only counter cache inspector.

    IMPORTANT: like_count / comment_count / share_count are NEVER editable here.
    They are maintained exclusively by Phase C signals using atomic F() updates.
    Editing them manually would break counter integrity.
    """

    list_display = (
        "content_type",
        "short_content_id",
        "like_count",
        "comment_count",
        "share_count",
        "updated_at",
    )
    list_filter = ("content_type",)
    ordering = ("-updated_at",)
    readonly_fields = (
        "content_type",
        "content_id",
        "like_count",
        "comment_count",
        "share_count",
        "updated_at",
    )
    list_per_page = 50

    def has_add_permission(self, request) -> bool:
        return False  # Rows are created lazily by signals only

    def has_change_permission(self, request, obj=None) -> bool:
        return False  # Counter integrity: only signals may write

    def has_delete_permission(self, request, obj=None) -> bool:
        return False  # Deleting a count row would corrupt the cache

    @admin.display(description="Content ID")
    def short_content_id(self, obj: SocialCount) -> str:
        return str(obj.content_id)[:8] + "…"
