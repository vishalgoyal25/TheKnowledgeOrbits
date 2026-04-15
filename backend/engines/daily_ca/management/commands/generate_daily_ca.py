"""
engines/daily_ca/management/commands/generate_daily_ca.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase K1 — generate_daily_ca management command.

Fetches approved CaDailyProposals for a given date and runs the full
DailyCaGeneratorService pipeline to produce DailyCaArticle records.
After all cycles: automatically triggers background static generation
for topics that had no published BookContent at generation time.

Usage:
    python manage.py generate_daily_ca
    python manage.py generate_daily_ca --date 2026-04-10
    python manage.py generate_daily_ca --date today
    python manage.py generate_daily_ca --date 2026-04-10 --database=supabase
    python manage.py generate_daily_ca --date today --auto-publish
    python manage.py generate_daily_ca --date today --auto-publish --database=supabase

Process:
  1. Fetch CaDailyProposal WHERE date=X AND status IN ('approved', 'queued_next_run')
  2. Order by relevance_score DESC
  3. Run DailyCaGeneratorService.run_generation_cycle()
     — each cycle: wiki check → static check → LLM → save article → tags → concepts
     — live progress printed per cycle
     — failed cycles logged + skipped, loop continues
     — session cap (25 GROQ calls) hit → remaining marked 'queued_next_run'
  4. Post-cycle: background static generation triggered automatically
  5. Final summary printed

Notes:
  - Re-running with the same date automatically picks up 'queued_next_run' proposals
  - Already 'generated' proposals are never re-processed
  - Does NOT auto-publish by default — human admin reviews before publishing
  - With --auto-publish: publishes all generated articles immediately after generation
  - Static generation runs in background while admin reviews articles
"""

from datetime import datetime

import sentry_sdk
import structlog
from django.core.management.base import BaseCommand
from django.utils import timezone

from engines.daily_ca.models import CaDailyProposal
from engines.daily_ca.services.generator_service import DailyCaGeneratorService

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = (
        "Generate Daily CA articles from approved proposals. "
        "Triggers background static generation post-cycle automatically."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            default="today",
            help=(
                "Date to generate articles for. "
                "Format: YYYY-MM-DD or 'today' (default: today)"
            ),
        )
        parser.add_argument(
            "--database",
            default="default",
            help="Database alias to use (default: 'default'). Use 'supabase' for production.",
        )
        parser.add_argument(
            "--auto-publish",
            action="store_true",
            default=False,
            help=(
                "Automatically publish all generated articles after generation completes. "
                "Without this flag, articles remain unpublished for manual review (default behaviour)."
            ),
        )

    def handle(self, *args, **options):
        db_alias: str = options["database"]
        date_str: str = options["date"].strip().lower()

        # ── Resolve date ──────────────────────────────────────────────────────
        if date_str == "today":
            target_date = timezone.now().date()
        else:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                self.stderr.write(
                    self.style.ERROR(
                        f"Invalid date format: '{date_str}'. Use YYYY-MM-DD or 'today'."
                    )
                )
                return

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\n{'━' * 60}\n"
                f"  Daily CA Generator — {target_date}\n"
                f"  Database: {db_alias}\n"
                f"{'━' * 60}"
            )
        )

        # ── Fetch proposals ───────────────────────────────────────────────────
        # Pick up both 'approved' (fresh) and 'queued_next_run' (capped from yesterday)
        proposals = list(
            CaDailyProposal.objects.using(db_alias)
            .filter(date=target_date, status__in=["approved", "queued_next_run"])
            .select_related("topic__subject")
            .order_by("-relevance_score")
        )

        if not proposals:
            already_generated = (
                CaDailyProposal.objects.using(db_alias)
                .filter(date=target_date, status="generated")
                .count()
            )
            self.stdout.write(
                self.style.WARNING(
                    f"\nNo approved or queued proposals found for {target_date}."
                )
            )
            if already_generated:
                self.stdout.write(
                    f"  ({already_generated} proposals already generated for this date.)\n"
                )
            else:
                self.stdout.write(
                    "  Run 'generate_ca_proposals' first to create proposals.\n"
                )
            return

        self.stdout.write(
            f"\nFound {len(proposals)} proposal(s) to process for {target_date}.\n"
        )

        # ── Monkey-patch generator to intercept cycle events for live output ──
        # We wrap run_generation_cycle to print live per-cycle progress.
        # This avoids changing the service's logging architecture.
        original_run_single = DailyCaGeneratorService._run_single_cycle

        cycle_counter = [0]
        total = len(proposals)

        @classmethod  # type: ignore[misc]
        def _instrumented_cycle(cls, proposal, db_alias="default"):
            cycle_counter[0] += 1
            n = cycle_counter[0]
            self.stdout.write(f"  Cycle {n}/{total} starting: {proposal.title[:70]}...")
            try:
                article, calls, needs_static = original_run_single.__func__(
                    cls, proposal, db_alias=db_alias
                )
                static_flag = "NO (queued for bg)" if needs_static else "YES"
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Cycle {n}/{total} DONE: {article.title[:60]}\n"
                        f"    │ Words: {len(article.body_md.split())} "
                        f"│ Quality: {article.quality_score}/10 "
                        f"│ Static anchor: {static_flag}"
                    )
                )
                return article, calls, needs_static
            except Exception as exc:
                self.stdout.write(
                    self.style.ERROR(
                        f"  Cycle {n}/{total} FAILED: {str(exc)[:100]} — continuing..."
                    )
                )
                raise  # re-raise so run_generation_cycle marks it 'failed'

        DailyCaGeneratorService._run_single_cycle = _instrumented_cycle

        # ── Run generation ────────────────────────────────────────────────────
        try:
            results = DailyCaGeneratorService.run_generation_cycle(
                proposals=proposals,
                groq_calls_used=0,
                db_alias=db_alias,
                auto_publish=options["auto_publish"],
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error("generate_daily_ca_command_failed", error=str(exc))
            self.stderr.write(self.style.ERROR(f"\nFatal error: {exc}"))
            return
        finally:
            # Always restore original method
            DailyCaGeneratorService._run_single_cycle = original_run_single

        # ── Post-cycle static trigger output ──────────────────────────────────
        static_triggered = results.get("static_triggered", 0)
        if static_triggered:
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"\nTriggering background static generation for "
                    f"{static_triggered} topic(s) without static content..."
                )
            )
            self.stdout.write(
                "  → Static will be ready for tomorrow's CA generation.\n"
            )
        elif results.get("generated", 0) > 0:
            self.stdout.write(
                "\n  All generated articles already had static content.\n"
            )

        # ── Session cap notice ────────────────────────────────────────────────
        if results.get("capped", 0):
            self.stdout.write(
                self.style.WARNING(
                    f"\n  Session cap reached. "
                    f"{results['capped']} proposal(s) marked as 'queued_next_run'.\n"
                    f"  They will be picked up automatically on the next scheduled run."
                )
            )

        # ── Final summary ─────────────────────────────────────────────────────
        auto_publish: bool = options["auto_publish"]
        generated = results.get("generated", 0)
        failed = results.get("failed", 0)
        capped = results.get("capped", 0)
        groq_used = results.get("groq_calls_used", 0)

        self.stdout.write(self.style.MIGRATE_HEADING(f"\n{'━' * 60}"))
        self.stdout.write(
            self.style.SUCCESS(
                f"  Generation complete: "
                f"{generated} generated | "
                f"{failed} failed | "
                f"{capped} queued | "
                f"GROQ calls: {groq_used}/{DailyCaGeneratorService.MAX_GROQ_CALLS}"
            )
        )
        if static_triggered:
            self.stdout.write(
                f"  Background static triggered for: {static_triggered} topic(s)"
            )
        if auto_publish:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Auto-publish: {generated} article(s) published (each published immediately after generation)."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "\n  Articles are NOT published yet.\n"
                    "  Review in Django admin → Daily CA → Articles → set is_published=True."
                )
            )
        self.stdout.write(self.style.MIGRATE_HEADING(f"{'━' * 60}\n"))

        logger.info(
            "generate_daily_ca_complete",
            date=str(target_date),
            db_alias=db_alias,
            auto_publish=auto_publish,
            **{k: v for k, v in results.items()},
        )
