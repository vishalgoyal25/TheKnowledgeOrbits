"""
engines/tags/management/commands/regenerate_concept_content.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
G3.12 (FEATURES_GROWTH_STACK.md §4.3 d, §7.11) — rewrite thin and broken
concept pages IN PLACE, a few a day, behind a kill switch.

WHAT IT PICKS
  READY pages (`is_content_ready=True`) whose stored body fails the G0.3 rule
  (`concept_seo_service.needs_regeneration`): < 400 words, < 3 headings, or
  the single-line "C7" shape. 555 such pages existed on 2026-09-14. Broken
  (single-line) pages go first, then by usage_count — the most-linked thin
  pages are the ones readers actually reach.

WHAT IT DOES
  Calls the same generator as new stubs, with force=True. The G3.11 gate
  inside the generator decides: a draft that passes REPLACES the thin body; a
  draft that fails is dropped and the row is left exactly as it was. The page
  can therefore only get better, never worse, and never disappears.

RAILS (same shape as the G3.9 overview cron)
  - Kill switch: env `CONCEPT_REGENERATION_ENABLED` (default off). The daily
    pipeline calls this command every run; with the switch off it exits at
    once. `--manual` bypasses the switch for an explicit hand run.
  - `--max N` (default 5) — hard cap on LLM calls per run (+ at most one retry
    each inside the generator).
  - Lock via cache.add — two overlapping runs cannot double-spend the budget.
  - `--dry-run` lists what would be rewritten and touches nothing.
  - Never deletes, never de-links, never touches the sitemap directly — the
    feed re-reads `is_indexable` on its next cache miss.

USAGE
  python manage.py regenerate_concept_content --dry-run --database=supabase
  python manage.py regenerate_concept_content --max 3 --manual --database=supabase
"""

import os

import sentry_sdk
import structlog
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandParser

from engines.tags.models import ConceptPage
from engines.tags.services.concept_content_service import ConceptContentService
from engines.tags.services.concept_seo_service import (
    needs_regeneration,
    quality_issues,
)

logger = structlog.get_logger(__name__)

KILL_SWITCH_ENV = "CONCEPT_REGENERATION_ENABLED"
DEFAULT_MAX = 5
LOCK_KEY = "tags:regenerate_concept_content:lock"
LOCK_TTL = 2 * 3600  # a run of 5 (+ retries) at 15 s/call is minutes, not hours


def _switch_on() -> bool:
    return os.getenv(KILL_SWITCH_ENV, "False").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _broken_first(concept: ConceptPage) -> tuple[int, int]:
    """Sort key: single-line bodies first, then the most-referenced."""
    issues = quality_issues(concept.body_md or "")
    broken = any("no newline" in i for i in issues)
    return (0 if broken else 1, -(concept.usage_count or 0))


class Command(BaseCommand):
    help = (
        "Rewrite thin/broken READY concept pages in place under --max N, behind "
        f"the {KILL_SWITCH_ENV} kill switch (G3.12)."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--max", type=int, default=DEFAULT_MAX, metavar="N")
        parser.add_argument("--database", default="default", help="DB alias")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--manual",
            action="store_true",
            help=f"Explicit hand run — bypass {KILL_SWITCH_ENV}",
        )

    def handle(self, *args, **options) -> None:
        db: str = options["database"]
        limit: int = max(0, options["max"])
        dry_run: bool = options["dry_run"]

        if not dry_run and not options["manual"] and not _switch_on():
            self.stdout.write(
                f"regenerate_concept_content: {KILL_SWITCH_ENV} is off — nothing done."
            )
            logger.info("concept_regeneration_disabled", database=db)
            return

        # ── Queue: every ready page failing the rule, broken first ───────────
        try:
            ready = ConceptPage.objects.using(db).filter(is_content_ready=True)
            queue = sorted(
                (c for c in ready.iterator(chunk_size=200) if needs_regeneration(c)),
                key=_broken_first,
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error(
                "concept_regeneration_scan_failed", database=db, error=str(exc)
            )
            self.stderr.write(self.style.ERROR(f"Scan failed: {exc}"))
            return

        batch = queue[:limit]
        self.stdout.write(
            f"Queue: {len(queue)} ready page(s) fail the rule on '{db}'; "
            f"this run: {len(batch)}."
        )
        logger.info(
            "concept_regeneration_queue",
            database=db,
            queue=len(queue),
            batch=len(batch),
            dry_run=dry_run,
        )

        if dry_run:
            for c in batch:
                self.stdout.write(
                    f"  would rewrite {c.slug}: {'; '.join(quality_issues(c.body_md))}"
                )
            return
        if not batch:
            return

        # ── Lock — one run at a time ─────────────────────────────────────────
        if not cache.add(LOCK_KEY, "1", timeout=LOCK_TTL):
            self.stdout.write("Another regeneration run holds the lock — exiting.")
            logger.info("concept_regeneration_locked", database=db)
            return

        rewritten = 0
        rejected = 0
        try:
            for idx, concept in enumerate(batch, start=1):
                before = "; ".join(quality_issues(concept.body_md))
                self.stdout.write(
                    f"  [{idx}/{len(batch)}] {concept.slug} ({before}) ... ", ending=""
                )
                try:
                    ok = ConceptContentService.generate_concept_content(
                        concept=concept, db_alias=db, force=True
                    )
                except Exception as exc:
                    sentry_sdk.capture_exception(exc)
                    logger.error(
                        "concept_regeneration_item_failed",
                        slug=concept.slug,
                        error=str(exc),
                    )
                    self.stdout.write(self.style.ERROR(f"ERROR — {exc}"))
                    rejected += 1
                    continue
                if ok:
                    rewritten += 1
                    self.stdout.write(self.style.SUCCESS("rewritten"))
                else:
                    rejected += 1
                    self.stdout.write(self.style.WARNING("rejected — old body kept"))
        finally:
            cache.delete(LOCK_KEY)

        self.stdout.write(
            f"Rewritten {rewritten}, rejected {rejected}, "
            f"remaining in queue ~{len(queue) - rewritten}."
        )
        logger.info(
            "concept_regeneration_done",
            database=db,
            rewritten=rewritten,
            rejected=rejected,
            remaining=len(queue) - rewritten,
        )
