"""
engines/daily_ca/management/commands/run_daily_pipeline.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase J2 — Full automation pipeline (zero human involvement).

Runs every day via Render Cron at 02:00 UTC (07:30 IST).
Replaces manual execution of three separate commands.

Pipeline (4 steps, sequential):
  Step 1 — generate_ca_proposals
             Reads last-24hr CAArticles → scores → groups by topic →
             creates up to 30 CaDailyProposal records (status="pending").
             Idempotent: skips topics that already have a proposal for today.

  Step 2 — auto-approve top N by relevance_score
             Picks top --top proposals (default 10) sorted by relevance_score DESC.
             Sets status="approved", approved_at=now().
             Skips proposals already approved/generated (idempotent).

  Step 3 — generate_daily_ca
             Reads status="approved" proposals → runs DailyCaGeneratorService
             for each → creates DailyCaArticle records.

  Step 4 — auto-publish
             Sets is_published=True on all articles generated in this run.

Usage:
    python manage.py run_daily_pipeline
    python manage.py run_daily_pipeline --top 10
    python manage.py run_daily_pipeline --database=supabase
    python manage.py run_daily_pipeline --top 10 --database=supabase
    python manage.py run_daily_pipeline --date 2026-04-10 --database=supabase

Notes:
  - Safe to re-run: each step is idempotent (skips already-processed records)
  - If scrape_ca hasn't run yet, Step 1 finds 0 articles and exits gracefully
  - --top is a soft cap: if fewer proposals were created, all of them are approved
  - All four steps share the same --date and --database arguments
"""

import sentry_sdk
import structlog
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime
from engines.daily_ca.models import CaDailyProposal

logger = structlog.get_logger(__name__)

_DIVIDER = "━" * 60


class Command(BaseCommand):
    help = (
        "Full Daily CA pipeline: proposals → auto-approve top N → "
        "generate articles → auto-publish. Designed for Render Cron."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            default="today",
            help="Target date. 'today' (default) or YYYY-MM-DD.",
        )
        parser.add_argument(
            "--top",
            type=int,
            default=10,
            help="Number of top proposals (by relevance_score) to auto-approve (default: 10).",
        )
        parser.add_argument(
            "--database",
            default="default",
            help="Database alias (default: 'default'). Use 'supabase' for production.",
        )

    def handle(self, *args, **options):
        db_alias: str = options["database"]
        date_str: str = options["date"].strip().lower()
        top_n: int = options["top"]

        # Resolve date once — shared by all steps
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
                f"\n{_DIVIDER}\n"
                f"  Daily CA Pipeline — {target_date}\n"
                f"  Database : {db_alias}\n"
                f"  Auto-approve top : {top_n} proposals\n"
                f"{_DIVIDER}"
            )
        )

        # ── STEP 1: Generate proposals ────────────────────────────────────────
        self.stdout.write(
            self.style.MIGRATE_HEADING("\n▶ Step 1/4 — Generating proposals...")
        )
        try:
            call_command(
                "generate_ca_proposals",
                date=options["date"],
                database=db_alias,
                stdout=self.stdout,
                stderr=self.stderr,
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error("pipeline_step1_failed", error=str(exc))
            self.stderr.write(
                self.style.ERROR(f"\n✗ Step 1 failed: {exc}\nPipeline aborted.")
            )
            return

        # ── STEP 2: Auto-approve top N by relevance_score ─────────────────────
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\n▶ Step 2/4 — Auto-approving top {top_n} proposals..."
            )
        )
        try:
            approved_count = self._auto_approve_top_n(
                target_date=target_date,
                top_n=top_n,
                db_alias=db_alias,
            )
            if approved_count == 0:
                self.stdout.write(
                    self.style.WARNING(
                        "\n  No pending proposals found to approve.\n"
                        "  Either Step 1 created 0 proposals, or all were already approved.\n"
                        "  Continuing to Step 3 (may find already-approved proposals)."
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n  ✓ Auto-approved {approved_count} proposal(s) "
                        f"(top {top_n} by relevance_score)."
                    )
                )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error("pipeline_step2_failed", error=str(exc))
            self.stderr.write(
                self.style.ERROR(f"\n✗ Step 2 failed: {exc}\nPipeline aborted.")
            )
            return

        # ── STEP 3 + 4: Generate articles + auto-publish ──────────────────────
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "\n▶ Step 3/4 — Generating articles from approved proposals..."
            )
        )
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "▶ Step 4/4 — Auto-publish enabled (--auto-publish flag active)"
            )
        )
        try:
            call_command(
                "generate_daily_ca",
                date=options["date"],
                database=db_alias,
                auto_publish=True,
                stdout=self.stdout,
                stderr=self.stderr,
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error("pipeline_step3_failed", error=str(exc))
            self.stderr.write(self.style.ERROR(f"\n✗ Step 3/4 failed: {exc}"))
            return

        # ── Final summary ─────────────────────────────────────────────────────
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\n{_DIVIDER}\n"
                f"  Pipeline complete for {target_date}.\n"
                f"  Articles are LIVE on /news.\n"
                f"{_DIVIDER}\n"
            )
        )
        logger.info(
            "daily_pipeline_complete",
            date=str(target_date),
            db_alias=db_alias,
            top_n=top_n,
        )

    # ── Step 2 helper ─────────────────────────────────────────────────────────

    def _auto_approve_top_n(
        self,
        target_date,
        top_n: int,
        db_alias: str,
    ) -> int:
        """
        Selects top N pending proposals for target_date ordered by relevance_score DESC.
        Updates their status to 'approved' and sets approved_at = now().

        Returns the count of proposals that were actually approved.

        Idempotent: only touches status='pending' proposals.
        Already-approved or already-generated proposals are untouched.
        """
        now = timezone.now()

        # Fetch top N pending proposals — ordered by score descending
        top_proposals = list(
            CaDailyProposal.objects.using(db_alias)
            .filter(date=target_date, status="pending")
            .order_by("-relevance_score")[:top_n]
        )

        if not top_proposals:
            return 0

        ids_to_approve = [p.id for p in top_proposals]

        updated = (
            CaDailyProposal.objects.using(db_alias)
            .filter(id__in=ids_to_approve, status="pending")
            .update(status="approved", approved_at=now)
        )

        logger.info(
            "pipeline_auto_approved",
            date=str(target_date),
            db_alias=db_alias,
            approved_count=updated,
            top_n=top_n,
            scores=[round(p.relevance_score, 2) for p in top_proposals],
        )

        # Print the approved titles for transparency in Render logs
        for p in top_proposals:
            self.stdout.write(f"    ✓ [{round(p.relevance_score, 1)}] {p.title[:70]}")

        return updated
