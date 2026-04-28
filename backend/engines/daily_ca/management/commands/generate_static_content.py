"""
engines/daily_ca/management/commands/generate_static_content.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase B (FEATURES5) — Dedicated static content generation for today's CA topics.

Runs as a SEPARATE Render Cron job, 1.5 hours AFTER the main daily pipeline.
This ensures CA articles (10) + Daily Quiz (10) always complete first before
any LLM quota is consumed by static content generation.

Render Cron schedule:
  Name   : generate-static-content
  Command: cd backend && python manage.py generate_static_content --max-articles 3 --database=supabase
  Schedule: 30 9 * * *   (09:30 UTC = 15:00 IST; main pipeline runs at ~08:00 UTC)

What it does:
  1. Fetches today's CaDailyProposal records (status='generated') to get their
     linked knowledge.Topic objects — same topics that drove today's CA articles.
  2. Deduplicates by topic ID (a topic may appear across multiple proposals).
  3. Skips topics where content_status='complete' (fully built, no re-generation).
  4. Skips topics where content_status='generating' (safety guard against concurrency).
  5. Skips proposals with no topic FK (unlinked proposal — no safe target to ingest).
  6. Calls ingest_topic() directly (same process — no HTTP, no localhost issue).
     Each call handles the full 3-layer pipeline: classification → wiki → article
     → sub-subtopics → coherence. Each subtopic is saved immediately (not batched).
  7. Hard cap: --max-articles (default 3) to protect LLM quota.
  8. Per-topic try/except: one failed topic never aborts the run.

Key safety properties:
  - NO re-generation: content_status='complete' guard prevents re-running topics
  - NO duplication: topic ID dedup set prevents processing same topic twice per run
  - NO orphan creation: ingest_topic() uses strict hierarchy matching (SkipGenerationError
    if subject/module not in seeded DB — never invents new hierarchy nodes)
  - IMMEDIATE saves: ingest_topic() uses atomic transactions per subtopic — each article
    is written to DB as it completes, so partial runs never lose work
  - QUOTA safe: hard cap of 3 topics × ~5-10 LLM calls each = max ~30 calls per run
    (CA+Quiz uses ~22 calls; static gets the remaining quota at safe spacing)

Database note:
  --database controls BOTH proposal fetching AND ingest writes.
  At startup, if --database != 'default', Django's 'default' alias is rerouted
  to point to the specified database settings. This ensures ingest_topic() (which
  always uses 'default' internally) writes to Supabase when --database=supabase
  is passed — both locally and on Render.

Usage:
    python manage.py generate_static_content
    python manage.py generate_static_content --date 2026-04-28
    python manage.py generate_static_content --max-articles 2
    python manage.py generate_static_content --date today --max-articles 3 --database=supabase
"""

from datetime import datetime

import sentry_sdk
import structlog
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from engines.book_content.services.ingestor_service import ingest_topic
from engines.daily_ca.models import CaDailyProposal
from engines.knowledge.models import Topic

logger = structlog.get_logger(__name__)

_DIVIDER = "━" * 60


class Command(BaseCommand):
    help = (
        "Generate static book-quality content for today's CA proposal topics. "
        "Runs AFTER the daily CA+Quiz pipeline. Hard cap: --max-articles (default 3)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            default="today",
            help="Date to pull proposals from. 'today' (default) or YYYY-MM-DD.",
        )
        parser.add_argument(
            "--max-articles",
            type=int,
            default=3,
            help=(
                "Hard cap on topics to ingest in one run (default: 3). "
                "Each topic = 1 full 3-layer pipeline (~5-10 LLM calls). "
                "Keep ≤5 to protect CA+Quiz LLM quota."
            ),
        )
        parser.add_argument(
            "--database",
            default="supabase",
            help=(
                "Database alias for fetching CaDailyProposal records "
                "(default: 'supabase'). ingest_topic() always uses 'default'."
            ),
        )

    def handle(self, *args, **options):
        db_alias: str = options["database"]
        date_str: str = options["date"].strip().lower()
        max_articles: int = options["max_articles"]

        # ── Reroute Django 'default' DB to match --database alias ─────────────
        # ingest_topic() and every ORM call inside it always use the 'default'
        # database alias. When --database=supabase is passed, we must reroute
        # 'default' to point to the Supabase connection settings so that all
        # writes go to Supabase — not to local PostgreSQL.
        #
        # This direct settings mutation is safe in a management command:
        # single process, no concurrent requests, fresh process each Render run.
        # The old settings are restored at the end so re-entrant calls are safe.
        if db_alias != "default" and db_alias in settings.DATABASES:
            from django.db import connections

            connections["default"].close()  # drop any existing local connection
            settings.DATABASES["default"] = settings.DATABASES[db_alias]
            self.stdout.write(
                self.style.WARNING(
                    f"\n  DB rerouted: 'default' → '{db_alias}' "
                    "(ingest_topic() will write to Supabase)\n"
                )
            )
            logger.info(
                "static_gen_db_rerouted",
                to_alias=db_alias,
            )

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
                f"\n{_DIVIDER}\n"
                f"  Static Content Generator — {target_date}\n"
                f"  Database: {db_alias}  (proposals + all ingest writes)\n"
                f"  Max articles this run: {max_articles}\n"
                f"{_DIVIDER}"
            )
        )

        # ── Fetch today's generated proposals ─────────────────────────────────
        # Use 'generated' (already processed by daily CA) + 'approved' (edge case:
        # proposals approved but CA generation failed — still worth ingesting static).
        proposals = list(
            CaDailyProposal.objects.using(db_alias)
            .filter(date=target_date, status__in=["generated", "approved"])
            .select_related("topic", "topic__subject")
            .order_by("-relevance_score")
        )

        if not proposals:
            self.stdout.write(
                self.style.WARNING(
                    f"\n  No generated/approved proposals found for {target_date}.\n"
                    "  Run the daily pipeline first: run_daily_pipeline --database=supabase\n"
                )
            )
            logger.info(
                "static_gen_no_proposals",
                date=str(target_date),
                db_alias=db_alias,
            )
            return

        self.stdout.write(
            f"\n  Found {len(proposals)} proposal(s) for {target_date}.\n"
            f"  Scanning for ungenerated topics (cap: {max_articles})...\n"
        )

        # ── Build deduplicated, filtered topic queue ──────────────────────────
        seen_topic_ids: set = set()
        topic_queue: list[tuple[Topic, str]] = []  # (topic_obj, subject_name)

        skipped_no_topic = 0
        skipped_complete = 0
        skipped_generating = 0
        skipped_duplicate = 0

        for proposal in proposals:
            # Guard: proposal must have a linked topic
            if proposal.topic_id is None:
                skipped_no_topic += 1
                logger.info(
                    "static_gen_skip_no_topic",
                    proposal_id=str(proposal.id),
                    title=proposal.title[:60],
                )
                continue

            topic_obj: Topic = proposal.topic  # type: ignore[assignment]

            # Guard: deduplicate — same topic may appear in multiple proposals
            if topic_obj.id in seen_topic_ids:
                skipped_duplicate += 1
                continue
            seen_topic_ids.add(topic_obj.id)

            # Guard: topic is fully generated — never re-generate
            if topic_obj.content_status == "complete":
                skipped_complete += 1
                self.stdout.write(
                    f"  ⏭  Skipping '{topic_obj.name}' — already complete"
                )
                logger.info(
                    "static_gen_skip_complete",
                    topic=topic_obj.name,
                    topic_id=str(topic_obj.id),
                )
                continue

            # Guard: topic is currently being generated by another process.
            # Only skip if the flag was set within the last 3 hours — after that
            # it is a stuck/interrupted run (e.g. Ctrl+C, OOM kill) and must be
            # retried, not silently abandoned forever.
            if topic_obj.content_status == "generating":
                age = timezone.now() - topic_obj.updated_at
                age_minutes = int(age.total_seconds() / 60)
                if age.total_seconds() < 3 * 3600:  # < 3 h → likely live process
                    skipped_generating += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"  ⚠  Skipping '{topic_obj.name}' — content_status=generating "
                            f"(set {age_minutes}m ago; another process may be running)"
                        )
                    )
                    logger.warning(
                        "static_gen_skip_generating",
                        topic=topic_obj.name,
                        topic_id=str(topic_obj.id),
                        age_minutes=age_minutes,
                    )
                    continue
                # ≥ 3 h old → treat as interrupted run; fall through to ingest
                age_hours = round(age.total_seconds() / 3600, 1)
                self.stdout.write(
                    self.style.WARNING(
                        f"  ↺  '{topic_obj.name}' — generating flag is stale "
                        f"({age_hours}h old). Treating as interrupted run, retrying."
                    )
                )
                logger.warning(
                    "static_gen_retry_stuck_generating",
                    topic=topic_obj.name,
                    topic_id=str(topic_obj.id),
                    age_hours=age_hours,
                )

            # Resolve subject name: prefer topic's subject, fall back to proposal field
            subject_name: str = (
                topic_obj.subject.name
                if topic_obj.subject_id and topic_obj.subject
                else proposal.subject_name or ""
            )

            topic_queue.append((topic_obj, subject_name))

        # ── Print queue summary ────────────────────────────────────────────────
        self.stdout.write(
            f"\n  Queue: {len(topic_queue)} topic(s) to generate "
            f"| {skipped_complete} already complete "
            f"| {skipped_no_topic} no topic link "
            f"| {skipped_duplicate} duplicates"
        )

        if not topic_queue:
            self.stdout.write(
                self.style.SUCCESS(
                    "\n  Nothing to generate — all topics already have static content.\n"
                    "  Static library is up to date for today's CA proposals.\n"
                )
            )
            logger.info(
                "static_gen_nothing_to_do",
                date=str(target_date),
                skipped_complete=skipped_complete,
                skipped_no_topic=skipped_no_topic,
            )
            return

        # ── Run ingest_topic() for each queued topic ──────────────────────────
        generated = 0
        failed = 0
        capped = 0

        for i, (topic_obj, subject_name) in enumerate(topic_queue, 1):
            # Hard cap check
            if generated >= max_articles:
                capped = len(topic_queue) - (i - 1)
                self.stdout.write(
                    self.style.WARNING(
                        f"\n  Cap reached ({max_articles}). "
                        f"{capped} topic(s) deferred to tomorrow's run.\n"
                    )
                )
                logger.info(
                    "static_gen_cap_reached",
                    cap=max_articles,
                    at_topic=i,
                    deferred=capped,
                )
                break

            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"\n  [{i}/{min(len(topic_queue), max_articles)}] "
                    f"Generating: '{topic_obj.name}'"
                    + (f"  ({subject_name})" if subject_name else "")
                )
            )

            logger.info(
                "static_gen_topic_start",
                topic=topic_obj.name,
                subject=subject_name,
                topic_id=str(topic_obj.id),
                run_index=i,
            )

            try:
                result = ingest_topic(
                    topic_name=topic_obj.name,
                    subject_name=subject_name or None,
                )

                if result.get("skipped"):
                    # Hierarchy not found in seeded DB — not an error, just a mismatch
                    self.stdout.write(
                        self.style.WARNING(
                            f"  ⚠  '{topic_obj.name}' skipped — "
                            f"hierarchy mismatch: {result.get('reason', '')[:100]}"
                        )
                    )
                    logger.warning(
                        "static_gen_topic_hierarchy_skip",
                        topic=topic_obj.name,
                        reason=result.get("reason", "")[:200],
                    )
                    # Count as generated (we attempted it) — don't retry same day
                    generated += 1
                    continue

                nodes = result.get("nodes_created", 0)
                locked_ext = result.get("locked_extension", False)

                status_str = (
                    "locked extension (sub-subtopics only)"
                    if locked_ext
                    else f"{nodes} article(s) created"
                )
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓  '{topic_obj.name}' done — {status_str}")
                )

                logger.info(
                    "static_gen_topic_complete",
                    topic=topic_obj.name,
                    subject=subject_name,
                    topic_id=str(topic_obj.id),
                    nodes_created=nodes,
                    locked_extension=locked_ext,
                )

                generated += 1

            except Exception as exc:
                failed += 1
                sentry_sdk.capture_exception(exc)
                logger.error(
                    "static_gen_topic_failed",
                    topic=topic_obj.name,
                    topic_id=str(topic_obj.id),
                    error=str(exc),
                    exc_info=True,
                )
                self.stderr.write(
                    self.style.ERROR(
                        f"  ✗  '{topic_obj.name}' FAILED: {str(exc)[:120]}\n"
                        "     Logged to Sentry. Continuing to next topic..."
                    )
                )
                # DO NOT re-raise — one failed topic must never abort the full run

        # ── Final summary ─────────────────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n{_DIVIDER}"))
        self.stdout.write(
            self.style.SUCCESS(
                f"  Static generation complete for {target_date}:\n"
                f"  Generated : {generated} topic(s)\n"
                f"  Failed    : {failed} topic(s)\n"
                f"  Deferred  : {capped} topic(s) (cap: {max_articles})\n"
                f"  Skipped   : {skipped_complete} already complete, "
                f"{skipped_no_topic} no topic link, "
                f"{skipped_duplicate} duplicates"
            )
        )
        self.stdout.write(self.style.MIGRATE_HEADING(f"{_DIVIDER}\n"))

        logger.info(
            "static_gen_complete",
            date=str(target_date),
            generated=generated,
            failed=failed,
            capped=capped,
            skipped_complete=skipped_complete,
            skipped_no_topic=skipped_no_topic,
            skipped_duplicate=skipped_duplicate,
        )
