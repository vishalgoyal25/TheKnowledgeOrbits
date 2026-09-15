"""
engines/book_content/signals.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
P3.4 — Redis cache invalidation signals.

subject_tree and subject_graph are cached for 1 hour (P1.2 + P3.4).
These signals bust the cache whenever the underlying data changes:
  - Topic.save()        → tree + graph for that subject may have changed
  - BookContent.save()  → tree quality_score nodes may have changed

Cache keys come from constants.py — the single definition the views use — so
a payload-version bump there can never leave these signals deleting the old
key while the views serve a new one.
"""

import structlog
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from engines.book_content.constants import (
    subject_graph_cache_key,
    subject_tree_cache_key,
)

logger = structlog.get_logger(__name__)


def _bust_subject_caches(subject_id: str) -> None:
    """Delete both tree and graph cache for a subject."""
    cache.delete(subject_tree_cache_key(subject_id))
    cache.delete(subject_graph_cache_key(subject_id))
    logger.info("book_cache_busted", subject_id=subject_id)


@receiver(post_save, sender="knowledge.Topic")
def on_topic_save(sender, instance, **kwargs):
    """
    Bust tree + graph cache when a Topic is saved.
    Topic changes affect both the tree hierarchy and the graph nodes.
    """
    subject_id = str(instance.subject_id) if instance.subject_id else None
    if subject_id:
        _bust_subject_caches(subject_id)


@receiver(post_save, sender="book_content.BookContent")
def on_book_content_save(sender, instance, **kwargs):
    """
    Bust tree cache when BookContent is saved.
    Tree nodes carry quality_score from BookContent — must refresh when content changes.
    """
    try:
        subject_id = str(instance.topic.subject_id)
        _bust_subject_caches(subject_id)
    except Exception:
        # topic or subject_id may be None on a new unsaved object — safe to skip
        pass
