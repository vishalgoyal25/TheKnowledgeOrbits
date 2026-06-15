"""
engines/research_agent/management/commands/cleanup_research_sessions.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Maintenance command — run periodically (cron / background-tasks scheduler;
scheduling is a Phase 13 deployment concern).

  1. ORPHAN RECOVERY (Risk #44 / #53): sessions stuck in 'running' for longer
     than --orphan-minutes are marked 'failed'. This happens when a worker dies
     mid-pipeline (dyno recycle, crash) — the session would otherwise hang
     'running' forever.

  2. RETENTION (Risk #25): sessions older than --retention-days are deleted
     (cascades to their report / logs / snapshots) to cap table growth.

Usage:
  python manage.py cleanup_research_sessions
  python manage.py cleanup_research_sessions --orphan-minutes 10 --retention-days 30
"""

from __future__ import annotations

from datetime import timedelta

import structlog
from django.core.management.base import BaseCommand
from django.utils import timezone

from engines.research_agent.constants import SessionStatus
from engines.research_agent.models.research_session import ResearchSession

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Recover orphaned 'running' sessions and purge old sessions."

    def add_arguments(self, parser):
        parser.add_argument("--orphan-minutes", type=int, default=10)
        parser.add_argument("--retention-days", type=int, default=30)

    def handle(self, *args, **options):
        now = timezone.now()

        # 1. Orphan recovery
        orphan_cutoff = now - timedelta(minutes=options["orphan_minutes"])
        orphaned = ResearchSession.objects.filter(
            status=SessionStatus.RUNNING,
            updated_at__lt=orphan_cutoff,
        )
        orphan_count = orphaned.update(
            status=SessionStatus.FAILED,
            error_message="orphan_recovery: worker died mid-run",
            updated_at=now,
        )
        if orphan_count:
            logger.warning("research_agent.cleanup.orphans_failed", count=orphan_count)
        self.stdout.write(self.style.SUCCESS(f"Orphans marked failed: {orphan_count}"))

        # 2. Retention purge (CASCADE deletes report / logs / snapshots)
        retention_cutoff = now - timedelta(days=options["retention_days"])
        old = ResearchSession.objects.filter(created_at__lt=retention_cutoff)
        old_count = old.count()
        old.delete()
        if old_count:
            logger.info("research_agent.cleanup.old_deleted", count=old_count)
        self.stdout.write(self.style.SUCCESS(f"Old sessions deleted: {old_count}"))
