import sys
import threading

import sentry_sdk
import structlog

from django.apps import AppConfig

logger = structlog.get_logger(__name__)

# Management commands that mutate the schema — skip startup backfill during these.
_SKIP_COMMANDS = frozenset({"migrate", "makemigrations", "test", "shell", "dbshell"})


def _startup_backfill() -> None:
    """
    Background thread: fill in missing embeddings for published Daily CA articles.

    Runs once on Django startup (Render deploy or local runserver).
    Handles all past Supabase articles that were published before the
    post_save signal was wired up — zero manual steps needed.

    Safety:
      - Only processes articles that have NO embedding yet (missing_ids diff).
      - Uses bulk_create(ignore_conflicts=True) — safe against concurrent signal fires.
      - Zero wasted tokens: skips anything already embedded.
    """
    try:
        from engines.content.models import Embedding
        from engines.content.services.embedding_service import EmbeddingService
        from engines.daily_ca.models import DailyCaArticle

        published_ids = set(
            DailyCaArticle.objects.filter(is_published=True).values_list(
                "id", flat=True
            )
        )
        if not published_ids:
            logger.debug("startup_backfill_daily_ca_nothing_published")
            return

        already_embedded_ids = set(
            Embedding.objects.filter(content_type="daily_ca_article").values_list(
                "content_id", flat=True
            )
        )
        missing_ids = published_ids - already_embedded_ids

        if not missing_ids:
            logger.debug(
                "startup_backfill_daily_ca_all_embedded",
                total=len(published_ids),
            )
            return

        logger.info(
            "startup_backfill_daily_ca_start",
            missing=len(missing_ids),
            total=len(published_ids),
        )

        articles = list(
            DailyCaArticle.objects.filter(id__in=missing_ids)
            .defer(
                "body_md",
                "body_md_processed",
                "generation_metadata",
                "ca_chunk_ids",
                "sources_used",
            )
            .order_by("-published_date")
        )

        BATCH_SIZE = 20
        created = 0

        for i in range(0, len(articles), BATCH_SIZE):
            batch = articles[i : i + BATCH_SIZE]
            texts = [f"{a.title} {a.news_context or ''}".strip() for a in batch]

            try:
                vectors = EmbeddingService.generate_embeddings_batch(texts)

                embedding_objs = [
                    Embedding(
                        content_type="daily_ca_article",
                        content_id=article.id,
                        vector=vector,
                        model_name=EmbeddingService.MODEL_NAME,
                    )
                    for article, vector in zip(batch, vectors)
                ]

                Embedding.objects.bulk_create(
                    embedding_objs,
                    ignore_conflicts=True,  # safe if signal already saved one concurrently
                )
                created += len(batch)

                logger.info(
                    "startup_backfill_daily_ca_batch_done",
                    batch=i // BATCH_SIZE + 1,
                    embedded=len(batch),
                    total_so_far=created,
                )

            except Exception as exc:
                sentry_sdk.capture_exception(exc)
                logger.error(
                    "startup_backfill_daily_ca_batch_failed",
                    batch_start=i,
                    error=str(exc),
                )
                # Continue to next batch — don't abort the whole backfill

        logger.info(
            "startup_backfill_daily_ca_done",
            created=created,
            missing=len(missing_ids),
        )

    except Exception as exc:
        # Broad catch: never crash Django startup over a backfill failure
        sentry_sdk.capture_exception(exc)
        logger.error("startup_backfill_daily_ca_fatal", error=str(exc))


class DailyCaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "engines.daily_ca"
    label = "daily_ca"
    verbose_name = "Daily CA"

    def ready(self):
        # Register post_save signal — auto-generates semantic embeddings
        # when a DailyCaArticle is published (admin or cron auto-publish).
        import engines.daily_ca.signals  # noqa: F401

        # Startup backfill — handle articles published before the signal existed.
        # Skip during schema-mutating management commands (migrate, makemigrations, …).
        argv0 = sys.argv[1] if len(sys.argv) > 1 else ""
        if argv0 not in _SKIP_COMMANDS:
            thread = threading.Thread(
                target=_startup_backfill,
                daemon=True,
                name="startup-backfill-daily-ca",
            )
            thread.start()
            logger.debug("startup_backfill_daily_ca_thread_started")
