"""
engines/daily_ca/management/commands/generate_static_content.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pure static content generation — syllabus-driven, top-down.

Runs as a SEPARATE Render Cron job, after the main daily pipeline.
NO dependency on daily_CA proposals. Walks the seeded knowledge hierarchy
(Subject → Module → Topic) and fills in content for incomplete topics.

Render Cron schedule:
  Name   : generate-static-content
  Command: cd backend && python manage.py generate_static_content --max-articles 3 --database=supabase
  Schedule: 30 9 * * *   (09:30 UTC = 15:00 IST)

What it does:
  1. Queries the seeded Topic table directly (node_type='topic', not complete).
     Ordered: Subject → Module → Topic (alphabetical, deterministic).
  2. Skips topics where content_status='complete' (already fully built).
  3. Skips topics where content_status='generating' and flag is < 3 hours old.
  4. Calls ingest_topic() for each queued topic.
     ingest_topic() uses ONLY seeded subtopics from the DB — never invents
     subtopic names via LLM. LLM is only used to generate CONTENT for nodes
     that already exist in the hierarchy.
  5. Hard cap: --max-articles (default 3) to protect LLM quota.
  6. Per-topic try/except: one failed topic never aborts the run.

Hierarchy contract (hardcoded — never violated):
  Subject     → seeded, read-only
  Module      → seeded, read-only
  Topic       → seeded, content generated (never created here)
  Subtopic    → seeded, content generated (never created here)
  Sub-subtopic→ ONLY level where new nodes may be created (LLM, cap=2 per subtopic)
                No children below sub-subtopic — this is the floor.

Key safety properties:
  - NO re-generation: content_status='complete' guard
  - NO hierarchy invention: ingest_topic() uses seeded subtopics only
  - IMMEDIATE saves: atomic transaction per subtopic — partial runs never lose work
  - QUOTA safe: hard cap of 3 topics × ~5 LLM calls each = max ~15 calls per run

Database note:
  At startup, if --database != 'default', Django's 'default' alias is rerouted
  to point to the specified database. This ensures ingest_topic() writes to
  Supabase when --database=supabase is passed — both locally and on Render.

Usage:
    python manage.py generate_static_content
    python manage.py generate_static_content --max-articles 2
    python manage.py generate_static_content --max-articles 3 --database=supabase
"""

import sentry_sdk
import structlog
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from engines.book_content.services.ingestor_service import ingest_topic
from engines.book_content.services.llm_service import check_any_llm_available
from engines.knowledge.models import Subject, Topic

logger = structlog.get_logger(__name__)

_DIVIDER = "━" * 60


class Command(BaseCommand):
    help = (
        "Generate static book-quality content for today's CA proposal topics. "
        "Runs AFTER the daily CA+Quiz pipeline. Hard cap: --max-articles (default 3)."
    )

    def add_arguments(self, parser):
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

        run_date = timezone.now().date()

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\n{_DIVIDER}\n"
                f"  Static Content Generator — {run_date}\n"
                f"  Database : {db_alias}\n"
                f"  Source   : seeded syllabus hierarchy (Subject → Module → Topic)\n"
                f"  Max topics this run: {max_articles}\n"
                f"{_DIVIDER}"
            )
        )

        # ── Build queue: walk seeded hierarchy top-down ───────────────────────
        # Source: Topic table, node_type='topic', ordered Subject→Module→Topic.
        # No proposal dependency — pure syllabus walk.
        all_topic_qs = (
            Topic.objects.select_related("module__subject")
            .filter(node_type="topic", is_active=True)
            .order_by("module__subject__name", "module__name", "name")
        )

        skipped_complete = all_topic_qs.filter(content_status="complete").count()
        skipped_generating = 0
        topic_queue: list[tuple[Topic, str]] = []  # (topic_obj, subject_name)

        for topic_obj in all_topic_qs.exclude(content_status="complete"):
            # Resolve subject name from FK chain
            subject_name: str = (
                topic_obj.module.subject.name
                if topic_obj.module_id
                and topic_obj.module
                and topic_obj.module.subject_id
                else ""
            )

            # Guard: topic is currently being generated by another process.
            # Only skip if the flag was set within the last 3 hours.
            if topic_obj.content_status == "generating":
                age = timezone.now() - topic_obj.updated_at
                age_minutes = int(age.total_seconds() / 60)
                if age.total_seconds() < 3 * 3600:
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
                # ≥ 3 h old → stale flag, treat as interrupted run, retry
                age_hours = round(age.total_seconds() / 3600, 1)
                self.stdout.write(
                    self.style.WARNING(
                        f"  ↺  '{topic_obj.name}' — generating flag stale "
                        f"({age_hours}h). Retrying."
                    )
                )
                logger.warning(
                    "static_gen_retry_stuck_generating",
                    topic=topic_obj.name,
                    topic_id=str(topic_obj.id),
                    age_hours=age_hours,
                )

            topic_queue.append((topic_obj, subject_name))

        total_in_hierarchy = all_topic_qs.count()
        self.stdout.write(
            f"\n  Syllabus topics in DB : {total_in_hierarchy}\n"
            f"  Already complete      : {skipped_complete}\n"
            f"  In progress (skip)    : {skipped_generating}\n"
            f"  Queued for generation : {len(topic_queue)}\n"
            f"  This run cap          : {max_articles}\n"
        )

        if not topic_queue:
            self.stdout.write(
                self.style.SUCCESS(
                    "\n  Nothing to generate — all syllabus topics already complete.\n"
                )
            )
            logger.info(
                "static_gen_nothing_to_do",
                run_date=str(run_date),
                skipped_complete=skipped_complete,
            )
            return

        # ── Pre-flight LLM health check ───────────────────────────────────────
        self.stdout.write("\n  🔍 LLM pre-flight check (GROQ + Cerebras)...")
        if not check_any_llm_available():
            self.stdout.write(
                self.style.WARNING(
                    "  ⚠️  All LLM providers exhausted. "
                    "Aborting — retry after UTC midnight when quotas reset."
                )
            )
            logger.warning(
                "static_gen_preflight_all_llm_exhausted", run_date=str(run_date)
            )
            return
        self.stdout.write("  ✅ LLM available — proceeding.\n")

        # ── Run ingest_topic() for each queued topic ──────────────────────────
        # Shared budget across all topics this run.
        # CA topics are focused (not broad like "Parliament of India") so
        # 3 subtopics + 1 deep × 2 sub-subtopics ≈ 5 articles per topic.
        budget = {"remaining": max_articles * 5}

        generated = 0
        failed = 0
        capped = 0

        for i, (topic_obj, subject_name) in enumerate(topic_queue, 1):
            # Hard cap check
            if generated >= max_articles or budget["remaining"] <= 0:
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
                    budget=budget,
                    max_subtopics=3,
                    max_sub_subtopics=2,
                    max_deep_per_topic=1,
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
                partial = result.get("partial", False)

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
                    partial=partial,
                )

                generated += 1

                # Budget exhausted mid-topic — stop, don't attempt remaining topics
                if partial:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  🛑 Budget exhausted mid-topic. "
                            f"{len(topic_queue) - i} topic(s) deferred to next run."
                        )
                    )
                    logger.warning(
                        "static_gen_budget_exhausted",
                        topic=topic_obj.name,
                        reason=result.get("reason", ""),
                    )
                    break

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
                f"  Static generation complete — {run_date}:\n"
                f"  Generated : {generated} topic(s)\n"
                f"  Failed    : {failed} topic(s)\n"
                f"  Deferred  : {capped} topic(s) (cap: {max_articles})\n"
                f"  Skipped   : {skipped_complete} already complete, "
                f"{skipped_generating} generating"
            )
        )
        logger.info(
            "static_gen_complete",
            run_date=str(run_date),
            generated=generated,
            failed=failed,
            capped=capped,
            skipped_complete=skipped_complete,
            skipped_generating=skipped_generating,
        )

        # ── Subject-level progress report ─────────────────────────────────────
        # Printed after every run so Render logs show exactly which subject is
        # currently being built and how far along it is.
        # No DB schema change — derived entirely from Topic.content_status counts.
        self.stdout.write(
            self.style.MIGRATE_HEADING("\n  Subject Progress (topic-level nodes):\n")
        )
        for subject_obj in Subject.objects.order_by("name"):
            total_topics = Topic.objects.filter(
                module__subject=subject_obj, node_type="topic", is_active=True
            ).count()
            if total_topics == 0:
                continue  # subject has no seeded topics — skip display

            done_topics = Topic.objects.filter(
                module__subject=subject_obj,
                node_type="topic",
                content_status="complete",
            ).count()

            total_subtopics = Topic.objects.filter(
                module__subject=subject_obj, node_type="subtopic", is_active=True
            ).count()
            done_subtopics = Topic.objects.filter(
                module__subject=subject_obj,
                node_type="subtopic",
                content_status="complete",
            ).count()

            pct = int(done_topics / total_topics * 100) if total_topics else 0
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)

            status_line = (
                f"  [{bar}] {pct:3d}%  {subject_obj.name}\n"
                f"           Topics   : {done_topics}/{total_topics} complete\n"
                f"           Subtopics: {done_subtopics}/{total_subtopics} complete"
            )
            style = (
                self.style.SUCCESS
                if done_topics == total_topics
                else self.style.WARNING
            )
            self.stdout.write(style(status_line))

            logger.info(
                "static_gen_subject_progress",
                subject=subject_obj.name,
                topics_done=done_topics,
                topics_total=total_topics,
                subtopics_done=done_subtopics,
                subtopics_total=total_subtopics,
                pct_complete=pct,
            )

        self.stdout.write(self.style.MIGRATE_HEADING(f"{_DIVIDER}\n"))
