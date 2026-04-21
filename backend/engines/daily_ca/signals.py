"""
engines/daily_ca/signals.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Auto-generate semantic embeddings for DailyCaArticle on publish.

Trigger: post_save on DailyCaArticle
Condition: is_published=True AND no embedding exists yet

Flow:
  Article saved with is_published=True (admin publish OR cron auto-publish)
      ↓
  Signal fires → spawns background thread (non-blocking)
      ↓
  Thread: generate 384-dim embedding from title + news_context
      ↓
  Save to content_embedding table (content_type="daily_ca_article")
      ↓
  Article now appears in semantic (vector) search results

Why background thread:
  Embedding generation takes 200–500ms (HF API) or 100ms (local).
  Running synchronously in the signal would block the admin save or
  cron pipeline. Thread makes it fire-and-forget.

Why get_or_create:
  Signal fires on every save (including minor field updates after publish).
  get_or_create ensures embedding is generated exactly once — skip if already done.

Text used for embedding: title + " " + news_context
  - title: 10-15 word UPSC article title
  - news_context: 3-sentence news summary
  Together they give the semantic fingerprint of the article.
"""

import threading

import sentry_sdk
import structlog
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = structlog.get_logger(__name__)


def _generate_and_save_embedding(article_id: str, text: str) -> None:
    """
    Background worker: generate embedding and save to content_embedding.
    Runs in a daemon thread — never blocks the request/cron pipeline.
    """
    try:
        from engines.content.models import Embedding
        from engines.content.services.embedding_service import EmbeddingService

        # Skip if already exists (idempotent — safe to call multiple times)
        if Embedding.objects.filter(
            content_type="daily_ca_article", content_id=article_id
        ).exists():
            logger.debug("daily_ca_embedding_already_exists", article_id=article_id)
            return

        vector = EmbeddingService.generate_embedding(text)

        Embedding.objects.get_or_create(
            content_type="daily_ca_article",
            content_id=article_id,
            defaults={
                "vector": vector,
                "model_name": EmbeddingService.MODEL_NAME,
            },
        )

        logger.info("daily_ca_embedding_created", article_id=article_id)

    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logger.error(
            "daily_ca_embedding_failed",
            article_id=article_id,
            error=str(exc),
        )


@receiver(post_save, sender="daily_ca.DailyCaArticle")
def on_daily_ca_article_save(sender, instance, **kwargs) -> None:
    """
    Generate semantic embedding when a DailyCaArticle is published.

    Fires on every save — guarded by:
      1. is_published check (skip drafts)
      2. get_or_create inside worker (skip if already embedded)

    Works for both:
      - Admin manual publish (ReviewAndPublishView sets is_published=True)
      - Cron auto-publish (generate_daily_ca command sets is_published=True)
    """
    if not instance.is_published:
        return  # Unpublished draft — skip

    # Build embedding text: title + news_context
    text = f"{instance.title} {instance.news_context or ''}".strip()
    if not text:
        return

    article_id = str(instance.id)

    # Fire-and-forget background thread — non-blocking
    thread = threading.Thread(
        target=_generate_and_save_embedding,
        args=(article_id, text),
        daemon=True,
        name=f"embed-daily-ca-{article_id[:8]}",
    )
    thread.start()

    logger.debug("daily_ca_embedding_thread_started", article_id=article_id)
