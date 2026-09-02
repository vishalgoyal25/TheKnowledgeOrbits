"""
Delete telemetry rows past their retention window.

Why this lives in engines/telemetry and not in run_daily_pipeline
────────────────────────────────────────────────────────────────
The obvious move was to fold the prune into daily_ca's pipeline, next to the
proven _prune_old_ca(). That would have meant a daily_ca command importing and
deleting telemetry models — cross-engine database access, which the project
forbids. Instead telemetry owns its own prune and it is CHAINED onto an
existing cron in render.yaml. Same schedule, no new Render service, engine
boundary intact.

Why the two tables have different windows
─────────────────────────────────────────
They answer different questions and have wildly different growth.

  VisitLog     operational — load, error paths, abuse. Useful for weeks, not
               years, and it is the high-volume table (~500 B/row on every
               qualifying request). Short window.

  ContentRead  readership history. Capped by the unique constraint to one row
               per reader, per item, per day, so it grows with actual readers
               rather than with traffic — a few MB a year. It is also the only
               record of what people read, which is exactly the thing you want
               a long baseline for. Long window.

A single blanket retention would either throw away readership history that
costs almost nothing to keep, or hoard request logs that cost a lot.

NON-FATAL by design
───────────────────
Exits 0 even on failure. It is chained onto a cron that does real work; a
retention problem must never mark that run as failed or stop what follows.
Failures go to Sentry and structlog instead.
"""

from datetime import timedelta
from typing import Any

import structlog
from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS
from django.utils import timezone

from engines.telemetry.models import ContentRead, VisitLog
from engines.telemetry.utils import env_int, report

logger = structlog.get_logger(__name__)

DEFAULT_VISIT_LOG_RETENTION_DAYS = 30
DEFAULT_CONTENT_READ_RETENTION_DAYS = 365


class Command(BaseCommand):
    help = "Delete telemetry rows older than their retention window."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            help="Database alias. The crons pass --database=supabase.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be deleted without deleting it.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        db_alias: str = options["database"]
        dry_run: bool = options["dry_run"]

        visit_days = env_int(
            "TELEMETRY_RETENTION_DAYS", DEFAULT_VISIT_LOG_RETENTION_DAYS
        )
        read_days = env_int(
            "TELEMETRY_READ_RETENTION_DAYS", DEFAULT_CONTENT_READ_RETENTION_DAYS
        )

        try:
            visits = self._prune(VisitLog, visit_days, db_alias, dry_run)
            reads = self._prune(ContentRead, read_days, db_alias, dry_run)
        except Exception as exc:  # noqa: BLE001 — retention must never fail the cron
            report(exc)
            logger.error("telemetry_prune_failed", error=str(exc)[:200])
            self.stdout.write(self.style.WARNING(f"Telemetry prune failed: {exc}"))
            return

        verb = "would delete" if dry_run else "deleted"
        self.stdout.write(
            self.style.SUCCESS(
                f"Telemetry prune ({db_alias}): {verb} "
                f"{visits} visit_log (>{visit_days}d), "
                f"{reads} content_read (>{read_days}d)"
            )
        )

    def _prune(self, model: Any, days: int, db_alias: str, dry_run: bool) -> int:
        """
        Delete one model's expired rows and return the count.

        Neither model has a ForeignKey and neither has signal receivers, so
        Django takes the fast bulk-DELETE path rather than loading every row
        into memory first. That is why this stays cheap even after a gap
        between runs.
        """
        cutoff = timezone.now() - timedelta(days=days)
        queryset = model.objects.using(db_alias).filter(created_at__lt=cutoff)

        if dry_run:
            return int(queryset.count())

        deleted, _ = queryset.delete()
        logger.info(
            "telemetry_pruned",
            table=model._meta.db_table,
            deleted=deleted,
            older_than_days=days,
            database=db_alias,
        )
        return int(deleted)
