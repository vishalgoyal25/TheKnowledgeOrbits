"""
backfill_slugs — mint a slug for every Subject / Module / Topic that has none.

WHY (G3.10)
  Migration 0007 backfilled the rows that existed when it ran. Rows created
  after that — by the ingestor, the seed command, admin — get a slug from the
  model's save(). Between "migration applied" and "new code deployed" there is
  a window where rows are created by the OLD code with slug = NULL, and a
  migration cannot run twice. This command can. It is also the regression tool:
  a row with a NULL slug in production is a bug, and this prints how many.

USAGE
  python manage.py backfill_slugs --database=supabase            # report + fix
  python manage.py backfill_slugs --database=supabase --dry-run  # report only

Idempotent. Only rows with slug IS NULL are touched, only the slug column is
written, and the same unique_slug() as save() and the migration is used.
"""

from django.core.management.base import BaseCommand, CommandParser

import structlog

from engines.knowledge.models import SLUG_MAX_LENGTH, Module, Subject, Topic
from engines.knowledge.services.slug_service import unique_slug

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Mint slugs for hierarchy rows that have none (idempotent)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--database", default="default", help="DB alias")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report NULL-slug counts without writing",
        )

    def handle(self, *args, **options) -> None:
        db: str = options["database"]
        dry_run: bool = options["dry_run"]
        total = 0

        for model in (Subject, Module, Topic):
            rows = (
                model.objects.using(db)
                .filter(slug__isnull=True)
                .order_by("order_index", "name", "id")
            )
            count = rows.count()
            logger.info(
                "backfill_slugs_scan",
                model=model.__name__,
                null_slugs=count,
                database=db,
                dry_run=dry_run,
            )
            if dry_run or count == 0:
                total += count
                continue

            for row in rows.iterator(chunk_size=200):
                row.slug = unique_slug(
                    model,
                    row.name,
                    max_length=SLUG_MAX_LENGTH,
                    using=db,
                    exclude_pk=row.pk,
                )
                # Plain column write — never touch updated_at or anything the
                # content pipeline reads.
                model.objects.using(db).filter(pk=row.pk).update(slug=row.slug)
            total += count

        logger.info("backfill_slugs_done", rows=total, database=db, dry_run=dry_run)
        self.stdout.write(
            f"{'Would mint' if dry_run else 'Minted'} {total} slug(s) on '{db}'."
        )
