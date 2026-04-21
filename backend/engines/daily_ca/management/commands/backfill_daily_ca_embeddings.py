"""
Management command: backfill_daily_ca_embeddings
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
One-time backfill: generate semantic embeddings for all DailyCaArticle records
that were published BEFORE the auto-embedding signal was wired up.

Going forward, new articles get embedded automatically via the post_save signal
in engines/daily_ca/signals.py. This command handles the historical backlog.

Usage:
    python manage.py backfill_daily_ca_embeddings
    python manage.py backfill_daily_ca_embeddings --batch-size 10
    python manage.py backfill_daily_ca_embeddings --dry-run

Safety:
    - Idempotent: skips articles that already have an embedding (get_or_create).
    - Re-runnable: run it multiple times — only missing embeddings are filled.
    - Dry run: --dry-run shows what would be processed without saving anything.
"""

import time

import sentry_sdk
import structlog
from django.core.management.base import BaseCommand

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Backfill semantic embeddings for all published DailyCaArticle records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=20,
            help="Number of articles to embed per batch (default: 20).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be processed without saving anything.",
        )

    def handle(self, *args, **options):
        from engines.content.models import Embedding
        from engines.content.services.embedding_service import EmbeddingService
        from engines.daily_ca.models import DailyCaArticle

        batch_size = options["batch_size"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN — no embeddings will be saved.")
            )

        # Find all published articles without an embedding
        published_ids = set(
            DailyCaArticle.objects.filter(is_published=True).values_list(
                "id", flat=True
            )
        )
        already_embedded_ids = set(
            Embedding.objects.filter(content_type="daily_ca_article").values_list(
                "content_id", flat=True
            )
        )
        missing_ids = published_ids - already_embedded_ids

        total = len(missing_ids)
        if total == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    "All published Daily CA articles already have embeddings. Nothing to do."
                )
            )
            return

        self.stdout.write(
            f"Found {total} published articles without embeddings. "
            f"Processing in batches of {batch_size}..."
        )

        if dry_run:
            for article_id in missing_ids:
                self.stdout.write(f"  Would embed: {article_id}")
            return

        # Fetch articles needing embeddings
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

        created = 0
        failed = 0

        for i in range(0, len(articles), batch_size):
            batch = articles[i : i + batch_size]

            texts = [f"{a.title} {a.news_context or ''}".strip() for a in batch]

            try:
                vectors = EmbeddingService.generate_embeddings_batch(texts)

                embedding_objs = []
                for article, vector in zip(batch, vectors):
                    embedding_objs.append(
                        Embedding(
                            content_type="daily_ca_article",
                            content_id=article.id,
                            vector=vector,
                            model_name=EmbeddingService.MODEL_NAME,
                        )
                    )

                # bulk_create with ignore_conflicts — safe if some were created by
                # a concurrent signal fire between our check and this insert.
                Embedding.objects.bulk_create(
                    embedding_objs,
                    ignore_conflicts=True,
                )
                created += len(batch)

                self.stdout.write(
                    f"  Batch {i // batch_size + 1}: embedded {len(batch)} articles "
                    f"(total so far: {created}/{total})"
                )

                # Brief pause between batches — avoid hammering the HF API
                if i + batch_size < len(articles):
                    time.sleep(1)

            except Exception as exc:
                sentry_sdk.capture_exception(exc)
                failed += len(batch)
                logger.error(
                    "backfill_batch_failed",
                    batch_start=i,
                    error=str(exc),
                )
                self.stdout.write(
                    self.style.ERROR(f"  Batch {i // batch_size + 1} FAILED: {exc}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nBackfill complete. Created: {created} | Failed: {failed}"
            )
        )
        if failed:
            self.stdout.write(
                self.style.WARNING(
                    "Re-run this command to retry failed batches (idempotent)."
                )
            )
