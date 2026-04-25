"""
engines/assessment/management/commands/generate_daily_quiz.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Management command — generate the Daily Public Quiz for a given date.

Reads the same CaDailyProposal records used by generate_daily_ca, so both
pipelines share one input source. The resulting Quiz is immediately public
(is_public=True, created_by=None) — no separate publish step needed.

Usage:
    python manage.py generate_daily_quiz
    python manage.py generate_daily_quiz --date 2026-04-25
    python manage.py generate_daily_quiz --date today
    python manage.py generate_daily_quiz --date today --database=supabase

Process:
  1. Resolve date (today or YYYY-MM-DD).
  2. Idempotency check — if quiz already exists for this date, print status and exit.
  3. Fetch CaDailyProposal WHERE date=X AND status IN ('approved', 'generated')
     ordered by relevance_score DESC.
  4. Run DailyQuizGeneratorService.generate_daily_quiz().
     — 1 LLM call per proposal → 1 question per proposal (up to 10).
     — Failed proposals logged + skipped; loop continues.
     — Source URLs appended to each explanation deterministically.
  5. Print final summary (quiz_id, questions generated, failed).

Notes:
  - Re-running the same date is safe — the service's idempotency check
    detects the existing quiz and returns early without duplicate creation.
  - Already 'generated' proposals are accepted as input so the quiz can
    run after generate_daily_ca has already updated proposal statuses.
  - Quiz is permanently stored in assessment_quiz — users can attempt it
    any day, re-attempt as many times as they want (no attempt limit).
"""

from datetime import datetime

import sentry_sdk
import structlog
from django.core.management.base import BaseCommand
from django.utils import timezone

from engines.daily_ca.models import CaDailyProposal
from engines.assessment.services.daily_quiz_service import DailyQuizGeneratorService

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = (
        "Generate the Daily Public Quiz (10 questions) from today's approved "
        "CA proposals. Quiz is immediately public — no publish step required."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            default="today",
            help="Date to generate quiz for. Format: YYYY-MM-DD or 'today' (default: today).",
        )
        parser.add_argument(
            "--database",
            default="default",
            help="Database alias (default: 'default'). Use 'supabase' for production.",
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
                f"  Daily Quiz Generator — {target_date}\n"
                f"  Database : {db_alias}\n"
                f"{'━' * 60}"
            )
        )

        # ── Fetch proposals (shared with generate_daily_ca) ───────────────────
        # Accept both 'approved' and 'generated' so this command can run
        # after or alongside generate_daily_ca without ordering dependency.
        proposals = list(
            CaDailyProposal.objects.using(db_alias)
            .filter(date=target_date, status__in=["approved", "generated"])
            .select_related("topic")
            .order_by("-relevance_score")
        )

        if not proposals:
            self.stdout.write(
                self.style.WARNING(
                    f"\nNo approved proposals found for {target_date}.\n"
                    "  Run 'generate_ca_proposals' + approve proposals first,\n"
                    "  or run 'run_daily_pipeline' which handles all steps.\n"
                )
            )
            return

        self.stdout.write(
            f"\n  Found {len(proposals)} proposal(s) for {target_date}.\n"
            f"  Generating up to 10 questions — 1 per proposal...\n"
        )

        # ── Run generation ────────────────────────────────────────────────────
        try:
            result = DailyQuizGeneratorService.generate_daily_quiz(
                proposals=proposals,
                pub_date=target_date,
                db_alias=db_alias,
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error("generate_daily_quiz_command_failed", error=str(exc))
            self.stderr.write(self.style.ERROR(f"\nFatal error: {exc}\n"))
            return

        # ── Result output ─────────────────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n{'━' * 60}"))

        if result.get("skipped"):
            self.stdout.write(
                self.style.WARNING(
                    f"  Quiz already exists for {target_date} — skipped.\n"
                    f"  Existing quiz ID: {result['quiz_id']}\n"
                    f"  Questions: {result['generated']}"
                )
            )
        elif result.get("quiz_id"):
            self.stdout.write(
                self.style.SUCCESS(
                    "  Daily Quiz generated successfully!\n"
                    f"  Quiz ID   : {result['quiz_id']}\n"
                    f"  Questions : {result['generated']} generated"
                    + (f" | {result['failed']} failed" if result.get("failed") else "")
                    + "\n  Status    : PUBLIC — users can attempt immediately"
                    + "\n  Re-attempt: ENABLED — no attempt limit"
                )
            )
            logger.info(
                "generate_daily_quiz_complete",
                date=str(target_date),
                db_alias=db_alias,
                quiz_id=result["quiz_id"],
                generated=result["generated"],
                failed=result.get("failed", 0),
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    f"  Quiz generation failed — 0 questions produced.\n"
                    f"  Failed proposals: {result.get('failed', 0)}\n"
                    f"  Check logs / Sentry for details."
                )
            )

        self.stdout.write(self.style.MIGRATE_HEADING(f"{'━' * 60}\n"))
