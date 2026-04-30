"""
engines/daily_ca/management/commands/run_daily_pipeline.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase J2 — Full automation pipeline (zero human involvement).

Runs every day via Render Cron at 02:00 UTC (07:30 IST).
Replaces manual execution of three separate commands.

Pipeline (5 steps, sequential):
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

  Step 5 — generate_daily_quiz
             Reads the same approved/generated proposals → runs
             DailyQuizGeneratorService → creates one public Quiz (10 questions).
             Quiz is immediately public (no separate publish step).
             Idempotent: skips if quiz for this date already exists.

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
from datetime import datetime

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from engines.assessment.models import Quiz
from engines.current_affairs.models import CAArticle
from engines.daily_ca.models import CaDailyProposal

logger = structlog.get_logger(__name__)

_DIVIDER = "━" * 60


class Command(BaseCommand):
    help = (
        "Full Daily pipeline: proposals → auto-approve → generate CA articles → "
        "auto-publish → generate Daily Public Quiz. Designed for Render Cron."
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
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help=(
                "Inspect only — no LLM calls, no DB writes, no approvals. "
                "Shows today's CA article count, existing proposals (by status), "
                "which proposals would be auto-approved, and whether a quiz "
                "already exists for today. Safe to run anytime."
            ),
        )

    def handle(self, *args, **options):
        db_alias: str = options["database"]
        date_str: str = options["date"].strip().lower()
        top_n: int = options["top"]
        dry_run: bool = options["dry_run"]

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

        # ── Dry-run: read-only inspection, zero LLM calls, zero DB writes ────
        if dry_run:
            self._dry_run_inspect(target_date, db_alias, top_n)
            return

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
                f"\n▶ Step 2/5 — Auto-approving top {top_n} proposals..."
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
                "\n▶ Step 3/5 — Generating articles from approved proposals..."
            )
        )
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "▶ Step 4/5 — Auto-publish enabled (--auto-publish flag active)"
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
            # Don't return — quiz generation can still proceed independently

        # ── STEP 5: Generate Daily Public Quiz ───────────────────────────────
        self.stdout.write(
            self.style.MIGRATE_HEADING("\n▶ Step 5/5 — Generating Daily Public Quiz...")
        )
        try:
            call_command(
                "generate_daily_quiz",
                date=options["date"],
                database=db_alias,
                stdout=self.stdout,
                stderr=self.stderr,
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error("pipeline_step5_failed", error=str(exc))
            self.stderr.write(
                self.style.ERROR(
                    f"\n✗ Step 5 failed: {exc}\n"
                    "  (CA articles unaffected — quiz generation is independent)"
                )
            )

        # ── Final summary ─────────────────────────────────────────────────────
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\n{_DIVIDER}\n"
                f"  Pipeline complete for {target_date}.\n"
                f"  CA Articles : LIVE on /news\n"
                f"  Daily Quiz  : LIVE on /quiz\n"
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

    # ── Dry-run helper ────────────────────────────────────────────────────────

    def _dry_run_inspect(self, target_date, db_alias: str, top_n: int) -> None:
        """
        Read-only pipeline inspection. Zero LLM calls. Zero DB writes.
        Shows exactly what the real run would do, using live Supabase data.
        """
        self.stdout.write(
            self.style.WARNING(
                f"\n{'━' * 60}\n"
                f"  🔍 DRY RUN — Daily CA Pipeline ({target_date})\n"
                f"  Database : {db_alias} | No writes, no LLM calls.\n"
                f"{'━' * 60}"
            )
        )

        # ── Step 1 preview: CA articles ingested in last 24 hr ───────────────
        from datetime import timedelta

        since = timezone.now() - timedelta(hours=24)
        try:
            raw_ca_count = (
                CAArticle.objects.using(db_alias).filter(created_at__gte=since).count()
            )
        except Exception:
            raw_ca_count = 0

        self.stdout.write(
            self.style.MIGRATE_HEADING("\n▶ Step 1 — Proposals (read-only):")
        )
        self.stdout.write(f"  CA articles ingested (last 24 hr): {raw_ca_count}")

        proposals_qs = CaDailyProposal.objects.using(db_alias).filter(date=target_date)
        status_counts: dict = {}
        for row in proposals_qs.values("status"):
            status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1

        if not status_counts:
            self.stdout.write(
                self.style.WARNING(
                    f"  No proposals found for {target_date}.\n"
                    "  Step 1 would run generate_ca_proposals to create them."
                )
            )
        else:
            for st, cnt in sorted(status_counts.items()):
                self.stdout.write(f"  {st:12s}: {cnt} proposal(s)")

        # ── Step 2 preview: which proposals would be auto-approved ───────────
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\n▶ Step 2 — Auto-approve top {top_n} (read-only):"
            )
        )
        pending: list[CaDailyProposal] = list(
            CaDailyProposal.objects.using(db_alias)
            .filter(date=target_date, status="pending")
            .order_by("-relevance_score")[:top_n]
        )
        if not pending:
            self.stdout.write("  No pending proposals — nothing to approve.")
        else:
            self.stdout.write(
                f"  Would approve {len(pending)} proposal(s) (sorted by score):"
            )
            for p in pending:
                self.stdout.write(
                    f"    [{round(p.relevance_score, 1):4.1f}] {p.title[:70]}"
                )

        # ── Step 3 preview: approved proposals queued for article generation ──
        self.stdout.write(
            self.style.MIGRATE_HEADING("\n▶ Step 3 — Article generation (read-only):")
        )
        approved: list[CaDailyProposal] = list(
            CaDailyProposal.objects.using(db_alias)
            .filter(date=target_date, status="approved")
            .order_by("-relevance_score")
        )
        if not approved:
            self.stdout.write(
                "  No approved proposals — Step 3 would wait for Step 2 output."
            )
        else:
            self.stdout.write(
                f"  {len(approved)} approved proposal(s) ready for article generation:"
            )
            for p in approved:
                self.stdout.write(
                    f"    [{round(p.relevance_score, 1):4.1f}] {p.title[:70]}"
                )

        # ── Step 5 preview: quiz ──────────────────────────────────────────────
        self.stdout.write(
            self.style.MIGRATE_HEADING("\n▶ Step 5 — Daily Quiz (read-only):")
        )
        try:
            date_label = target_date.strftime("%d %B %Y")
            quiz_title = f"Daily Current Affairs Quiz — {date_label}"
            quiz_exists = (
                Quiz.objects.using(db_alias)
                .filter(title=quiz_title, is_public=True, created_by=None)
                .exists()
            )
            if quiz_exists:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✅ Quiz already exists for {target_date} — Step 5 would skip."
                    )
                )
            else:
                self.stdout.write(
                    f"  No quiz yet for {target_date} — Step 5 would generate one."
                )
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"  Quiz check failed: {exc}"))

        # ── Summary ───────────────────────────────────────────────────────────
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'━' * 60}\n"
                f"  ✅ Dry run complete — DB connection healthy.\n"
                f"  Run without --dry-run tomorrow to execute the full pipeline.\n"
                f"{'━' * 60}\n"
            )
        )
        logger.info(
            "daily_pipeline_dry_run",
            date=str(target_date),
            db_alias=db_alias,
            raw_ca_last24h=raw_ca_count,
            proposal_statuses=status_counts,
            pending_to_approve=len(pending),
            already_approved=len(approved),
        )
