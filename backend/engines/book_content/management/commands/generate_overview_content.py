"""
engines/book_content/management/commands/generate_overview_content.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
G3.9 (FEATURES_GROWTH_STACK.md §7.9a) — one run = ONE SUBJECT and all of its
modules, each getting a short introductory overview. 14 subjects → 14 days.

Runs on its own Render cron (05:30 UTC, `overview-content` in render.yaml),
never inside the article cron. There is no "generate all" path: `--max` is
the number of SUBJECTS this run may do and defaults to 1.

STEPS (each failure exits 0 with a log line and nothing written)
  1. kill switch  env OVERVIEW_GENERATION_ENABLED (default off) — `--manual`
                  bypasses it for an explicit hand run
  2. pre-flight   check_any_llm_available() — the #17-fixed one
  3. lock         cache.add("overview_generation_lock", 2 h) — its own key,
                  not the article cron's
  4. queue        overview_service.next_subject_batch() — recomputed from the
                  tables every run, so a module skipped for lack of articles
                  is picked up later and a newly seeded subject is picked up
                  the next morning
  5. generate     subject first, then its modules; one LLM call each (+ at
                  most one retry inside the service); a draft that fails the
                  gate writes nothing
  6. publish      rows land is_published=False unless `--auto-publish` or env
                  OVERVIEW_AUTO_PUBLISH=True — flip the env after the first
                  subject has been read by hand in admin

USAGE
  python manage.py generate_overview_content --dry-run --database=supabase
  python manage.py generate_overview_content --manual --database=supabase
  python manage.py generate_overview_content --manual --auto-publish --database=supabase
"""

import os

import sentry_sdk
import structlog
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandParser

from engines.book_content.services import overview_service
from engines.book_content.services.llm_service import check_any_llm_available

logger = structlog.get_logger(__name__)

KILL_SWITCH_ENV = "OVERVIEW_GENERATION_ENABLED"
AUTO_PUBLISH_ENV = "OVERVIEW_AUTO_PUBLISH"
LOCK_KEY = "overview_generation_lock"
LOCK_TTL = 2 * 3600


def _flag(name: str) -> bool:
    return os.getenv(name, "False").strip().lower() in {"1", "true", "yes", "on"}


class Command(BaseCommand):
    help = (
        "Generate introductory overviews for ONE subject and its modules per run "
        f"(G3.9). Kill switch: {KILL_SWITCH_ENV}."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--max", type=int, default=1, metavar="SUBJECTS", help="Subjects per run"
        )
        parser.add_argument("--database", default="default", help="DB alias")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--manual", action="store_true", help=f"Bypass {KILL_SWITCH_ENV}"
        )
        parser.add_argument(
            "--auto-publish",
            action="store_true",
            help=f"Publish rows on write (also: {AUTO_PUBLISH_ENV}=True)",
        )

    def handle(self, *args, **options) -> None:
        db: str = options["database"]
        subjects_max: int = max(0, options["max"])
        dry_run: bool = options["dry_run"]
        publish: bool = options["auto_publish"] or _flag(AUTO_PUBLISH_ENV)

        summary = overview_service.pending_summary(db)
        self.stdout.write(
            "Overviews: subjects {subjects_done}/{subjects_total}, "
            "modules {modules_done}/{modules_total} on '{db}'.".format(db=db, **summary)
        )

        if dry_run:
            batch = overview_service.next_subject_batch(db)
            if not batch:
                self.stdout.write("Nothing pending.")
                return
            for t in batch:
                n = overview_service.generated_articles_under(t, db).count()
                self.stdout.write(f"  would write {t.key}  {t.name}  (grounded on {n})")
            return

        if not options["manual"] and not _flag(KILL_SWITCH_ENV):
            self.stdout.write(f"{KILL_SWITCH_ENV} is off — nothing done.")
            logger.info("overview_generation_disabled", database=db)
            return

        if not check_any_llm_available():
            self.stdout.write("No LLM provider reachable — skipping today.")
            logger.warning("overview_skipped_no_llm", database=db)
            return

        if not cache.add(LOCK_KEY, "1", timeout=LOCK_TTL):
            self.stdout.write("Another overview run holds the lock — exiting.")
            logger.info("overview_generation_locked", database=db)
            return

        written = 0
        rejected = 0
        try:
            for _ in range(subjects_max):
                batch = overview_service.next_subject_batch(db)
                if not batch:
                    self.stdout.write("Nothing pending.")
                    logger.info("overview_nothing_pending", database=db)
                    break
                subject_name = batch[0].subject_name
                self.stdout.write(f"▶ {subject_name}: {len(batch)} node(s)")
                for t in batch:
                    self.stdout.write(f"  {t.key}  {t.name} ... ", ending="")
                    try:
                        row = overview_service.generate_overview(t, db, publish=publish)
                    except (
                        Exception
                    ) as exc:  # the service should never raise; belt and braces
                        sentry_sdk.capture_exception(exc)
                        logger.error(
                            "overview_item_failed", target=t.key, error=str(exc)
                        )
                        row = None
                    if row is None:
                        rejected += 1
                        self.stdout.write(self.style.WARNING("nothing written"))
                    else:
                        written += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"{row.word_count} words"
                                + (" (published)" if publish else " (draft)")
                            )
                        )
        finally:
            cache.delete(LOCK_KEY)

        self.stdout.write(f"Written {written}, nothing-written {rejected}.")
        logger.info(
            "overview_generation_done",
            database=db,
            written=written,
            rejected=rejected,
            published=publish,
        )
