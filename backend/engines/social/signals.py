"""
engines/social/signals.py
━━━━━━━━━━━━━━━━━━━━━━━━━
Social Interaction Engine — Signal Handlers (Phase C).

Two responsibilities:

1. SocialCount cache — atomic F() increments/decrements on every social event:
     Like created       → like_count    + 1
     Like deleted       → like_count    - 1  (floor 0 via Greatest)
     Comment created    → comment_count + 1  (only if not soft-deleted on create)
     Comment soft-del   → comment_count - 1  (pre_save detects the transition)
     Share created      → share_count   + 1

   Pattern: get_or_create (lazy init) → filter(pk).update(F()) — never reads count
   before writing. Safe under concurrent load.

2. UserEvent fire-and-forget — logs social activity to userstate.UserEvent
   for analytics after every creation event.
   Wrapped in try/except — failure NEVER blocks or rolls back the social action.
"""

import structlog
from django.db.models import F
from django.db.models.functions import Greatest
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from engines.social.models import Comment, Like, Share, SocialCount

logger = structlog.get_logger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _get_or_init_count(content_type: str, content_id) -> SocialCount:
    """
    Return the SocialCount row for (content_type, content_id), creating it
    with all-zero counts if it doesn't exist yet (lazy initialisation).
    """
    obj, _ = SocialCount.objects.get_or_create(
        content_type=content_type,
        content_id=content_id,
    )
    return obj


def _log_user_event(user, event_type: str, content_type: str, content_id) -> None:
    """
    Fire-and-forget: create a UserEvent row for analytics.
    Any exception is caught and logged as a warning — never propagated.
    """
    try:
        from engines.userstate.models import UserEvent  # noqa: PLC0415

        UserEvent.objects.create(
            user=user,
            event_type=event_type,
            event_data={
                "content_type": content_type,
                "content_id": str(content_id),
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "social_user_event_failed",
            event_type=event_type,
            content_type=content_type,
            content_id=str(content_id),
            error=str(exc),
        )


# ── Like signals ──────────────────────────────────────────────────────────────


@receiver(post_save, sender=Like)
def on_like_saved(sender, instance: Like, created: bool, **kwargs) -> None:
    """Like created → increment like_count + log UserEvent."""
    if not created:
        return

    count_obj = _get_or_init_count(instance.content_type, instance.content_id)
    SocialCount.objects.filter(pk=count_obj.pk).update(like_count=F("like_count") + 1)
    logger.info(
        "social_like_added",
        content_type=instance.content_type,
        content_id=str(instance.content_id),
        user_id=str(instance.user_id),
    )
    _log_user_event(
        instance.user, "like_added", instance.content_type, instance.content_id
    )


@receiver(post_delete, sender=Like)
def on_like_deleted(sender, instance: Like, **kwargs) -> None:
    """Like deleted (unlike) → decrement like_count, floor at 0."""
    SocialCount.objects.filter(
        content_type=instance.content_type,
        content_id=instance.content_id,
    ).update(like_count=Greatest(F("like_count") - 1, 0))
    logger.info(
        "social_like_removed",
        content_type=instance.content_type,
        content_id=str(instance.content_id),
        user_id=str(instance.user_id),
    )


# ── Comment signals ───────────────────────────────────────────────────────────
#
# Soft-delete detection requires two signals:
#   pre_save  — snapshot the current is_deleted value BEFORE the update
#   post_save — compare with the new value to detect the False → True transition


@receiver(pre_save, sender=Comment)
def on_comment_pre_save(sender, instance: Comment, **kwargs) -> None:
    """
    Cache is_deleted state before save so post_save can detect a soft-delete
    transition (False → True) versus a regular field edit.
    """
    if instance.pk:
        try:
            setattr(
                instance,
                "_pre_save_is_deleted",
                Comment.objects.get(pk=instance.pk).is_deleted,
            )
        except Comment.DoesNotExist:
            setattr(instance, "_pre_save_is_deleted", False)
    else:
        # New instance — no previous state
        setattr(instance, "_pre_save_is_deleted", False)


@receiver(post_save, sender=Comment)
def on_comment_saved(sender, instance: Comment, created: bool, **kwargs) -> None:
    """
    Comment created (visible) → increment comment_count + log UserEvent.
    Comment soft-deleted       → decrement comment_count, floor at 0.
    Comment edited             → no counter change.
    """
    if created:
        if instance.is_deleted:
            # Edge case: comment created already soft-deleted — skip counter
            return
        count_obj = _get_or_init_count(instance.content_type, instance.content_id)
        SocialCount.objects.filter(pk=count_obj.pk).update(
            comment_count=F("comment_count") + 1
        )
        logger.info(
            "social_comment_posted",
            content_type=instance.content_type,
            content_id=str(instance.content_id),
            comment_id=str(instance.pk),
            user_id=str(instance.user_id),
        )
        _log_user_event(
            instance.user, "comment_posted", instance.content_type, instance.content_id
        )
        return

    # Existing comment — detect soft-delete transition only
    old_deleted = getattr(instance, "_pre_save_is_deleted", False)
    if not old_deleted and instance.is_deleted:
        SocialCount.objects.filter(
            content_type=instance.content_type,
            content_id=instance.content_id,
        ).update(comment_count=Greatest(F("comment_count") - 1, 0))
        logger.info(
            "social_comment_soft_deleted",
            content_type=instance.content_type,
            content_id=str(instance.content_id),
            comment_id=str(instance.pk),
        )


# ── Share signals ─────────────────────────────────────────────────────────────


@receiver(post_save, sender=Share)
def on_share_saved(sender, instance: Share, created: bool, **kwargs) -> None:
    """Share created → increment share_count + log UserEvent."""
    if not created:
        return

    count_obj = _get_or_init_count(instance.content_type, instance.content_id)
    SocialCount.objects.filter(pk=count_obj.pk).update(share_count=F("share_count") + 1)
    logger.info(
        "social_share_logged",
        content_type=instance.content_type,
        content_id=str(instance.content_id),
        platform=instance.platform,
        user_id=str(instance.user_id),
    )
    _log_user_event(
        instance.user, "share_clicked", instance.content_type, instance.content_id
    )
