"""
generate_book_content.py — TheKnowledgeOrbits Book Content Engine Cockpit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Django management command equivalent of POC's run_lab.py.
Single entry point for the entire 3-Layer Quality Pipeline.

USAGE:
  Mode A (topic name):
    python manage.py generate_book_content
    python manage.py generate_book_content --topic "Parliament of India"
    python manage.py generate_book_content --subject "Indian Constitution & Polity"

  Mode B (NCERT PDF):
    Drop a PDF into data/input_pdfs/ and uncomment its path in PDF_FILES_TO_INGEST below.
    Set PDF_MODE = True.

  Dry run (no LLM calls):
    python manage.py generate_book_content --dry-run

WHAT IT DOES:
  1. Verifies DB state (all required tables exist)
  2. Generates/Retrieves Book Intelligence Plan (Layer 1)
  3. Runs the 3-Layer Quality Engine for each topic/PDF (Layer 2 + 3)
  4. Prints a full DB summary with quality metrics
  5. Handles GROQ rate limits gracefully (12s delay built into llm_service)
  6. Smart resumption: skips already-generated content (crash-safe)
"""

import sentry_sdk
import structlog
from django.core.management.base import BaseCommand, CommandError

from engines.book_content.models import BookContent, GenerationLog
from engines.book_content.services.book_planner_service import (
    generate_book_plan,
    get_book_plan,
)
from engines.book_content.services.ingestor_service import ingest_topic
from engines.book_content.services.llm_service import check_any_llm_available
from engines.knowledge.models import Subject, Topic

logger = structlog.get_logger(__name__)


# ══════════════════════════════════════════════════════════════════
# ⚙️  CONFIGURE YOUR INGESTION HERE
# ══════════════════════════════════════════════════════════════════

# ── SUBJECT CONFIGURATION ─────────────────────────────────────────────────────
# Mirrors run_lab.py MODULES config from POC.
# Add more subjects here as content generation expands.

SUBJECT_MODULES = {
    "Indian Polity & Constitution": [
        "Union Legislature",
        "Union Executive",
        "Union Judiciary",
        "State Government",
        "Fundamental Rights & Duties",
        "Directive Principles",
        "Constitutional Amendments",
        "Emergency Provisions",
        "Federalism & Centre-State Relations",
        "Constitutional Bodies",
    ],
}

# ── MODE A: Topic strings ──────────────────────────────────────────────────
# Uncomment topics to ingest. Run one at a time first for verification.
# All topics are registered in services/cross_subject_map.py (instant classification).

TOPICS_TO_GENERATE = [
    # ── POLITY CORE (start here — most UPSC weight) ───────────────────
    "Parliament of India",  # ← ACTIVE: first test
    # "President of India",
    # "Prime Minister of India",
    # "Cabinet Committees",
    # "Fundamental Rights",
    # "Directive Principles of State Policy",
    # "Preamble of Indian Constitution",
    # "Judicial Review & Judicial Activism",
    # "Election Process & Electoral Reforms",
    # "Federalism & Centre-State Relations",
    # "Federalism & Local Governance",
    # "Indian Constitution & Freedom Struggle Legacy",
    # "Indian Constitution & Governance",
    # ── ECONOMY & FINANCE ─────────────────────────────────────────────
    # "Budget & Fiscal Policy",               # Cross: Polity + Governance
    # "Economic Development & Growth",
    # "Poverty & Inequality",
    # "Agricultural Reforms",                 # Cross: Geography + Polity
    # "Food Security",                        # Cross: Geography + Governance
    # "Infrastructure Development",
    # "Industrial Policy",
    # "Trade & WTO",                          # Cross: IR + Polity
    # "Globalization & Its Impact",           # Cross: IR + Society
    # "Startup Ecosystem & Innovation",       # Cross: Science & Tech
    # "Land Reforms",                         # Cross: History + Polity
    # "Energy Security",                      # Cross: Geography + IR + Environment
    # ── GOVERNANCE & SOCIAL JUSTICE ───────────────────────────────────
    # "Social Justice (SC/ST/OBC)",           # Cross: Polity + History
    # "Women Empowerment",                    # Cross: Polity + Economy
    # "NGOs & Civil Society",
    # "Health Sector in India",               # Cross: Economy + Science
    # "Education System in India",            # Cross: Economy + Governance
    # "Ethics, Integrity & Aptitude",
    # ── ENVIRONMENT & GEOGRAPHY ───────────────────────────────────────
    # "Climate Change",                       # Cross: Geography + Economy + IR
    # "Environment & Agriculture Linkage",    # Cross: Economy + Geography
    # "Water Resource Management",            # Cross: Polity + Economy + Environment
    # "Disaster Management",                  # Cross: Geography + Governance
    # "Urbanization",                         # Cross: Economy + Environment
    # "Population & Demographics",            # Cross: Economy + Governance
    # "Migration (Internal & International)", # Cross: IR + Economy
    # ── SCIENCE & TECHNOLOGY ──────────────────────────────────────────
    # "Science & Technology in Governance",   # Cross: Polity + Governance
    # "Cyber Security",                       # Cross: Security + Polity
    # "Space Technology",                     # Cross: IR + Security
    # "Biotechnology",                        # Cross: Environment + Ethics
    # ── INTERNATIONAL RELATIONS ───────────────────────────────────────
    # "India's Foreign Policy",               # Cross: History + Geography + Economy
    # "Border Issues & Disputes",             # Cross: Geography + Security + History
    # "Regional Organizations (SAARC, ASEAN, SCO)", # Cross: Economy + Geography
    # ── INTERNAL SECURITY ─────────────────────────────────────────────
    # "Internal Security (Terrorism & Naxalism)", # Cross: Geography + Polity
]

# ── MODE B: NCERT PDFs (NCERT as spine + Wikipedia as enricher) ───────────
# Drop PDFs into data/input_pdfs/ first, then uncomment the path below.
PDF_FILES_TO_INGEST: list[str] = [
    # "data/input_pdfs/ncert_polity_ch22_parliament.pdf",
    # "data/input_pdfs/ncert_polity_ch17_president.pdf",
    # "data/input_pdfs/ncert_polity_ch13_fundamental_rights.pdf",
    # "data/input_pdfs/ncert_economy_ch01_development.pdf",
    # "data/input_pdfs/ncert_geography_ch01_resources.pdf",
]

# ── SHARED CONFIG ──────────────────────────────────────────────────────────
PDF_MODE = False  # Set to True to enable PDF ingestion (Mode B) — future feature

# ══════════════════════════════════════════════════════════════════


class Command(BaseCommand):
    """Generate book-quality UPSC study content using the 3-Layer Quality Engine."""

    help = (
        "Generate static book-quality UPSC articles using the 3-Layer Quality Engine."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--subject",
            type=str,
            default=None,
            help="Subject name to generate book plan for. "
            "Example: 'Indian Constitution & Polity'",
        )
        parser.add_argument(
            "--topic",
            type=str,
            default=None,
            help="Single topic name to generate. Overrides TOPICS_TO_GENERATE list.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Show what would be generated without making any LLM calls.",
        )
        parser.add_argument(
            "--max-topics",
            type=int,
            default=2,
            help="Maximum number of topics (chapters) to process per run (default: 2).",
        )
        parser.add_argument(
            "--max-actual-articles",
            type=int,
            default=15,
            help=(
                "Hard cap on total individual articles generated across ALL topics "
                "(default: 15). Shared with daily_ca + quiz cron — keep low."
            ),
        )
        parser.add_argument(
            "--max-subtopics-per-topic",
            type=int,
            default=4,
            help="Cap on subtopics processed per topic (default: 4).",
        )
        parser.add_argument(
            "--max-sub-subtopics-per-subtopic",
            type=int,
            default=3,
            help=(
                "Cap on sub-subtopics per subtopic (default: 3). "
                "Worst case: 4 subtopics × 2 deep × 3 sub-subtopics = ~10 articles/topic."
            ),
        )
        parser.add_argument(
            "--max-deep-per-topic",
            type=int,
            default=2,
            help=(
                "Max subtopics allowed deep-expansion (sub-subtopics) per topic "
                "(default: 2). Prevents all subtopics triggering sub-subtopic chains."
            ),
        )

    def handle(self, *args, **options):
        """Main entry point — equivalent to run_lab.py main()."""
        logger.info(
            "book_content_generation_started",
            subject=options.get("subject"),
            topic=options.get("topic"),
            dry_run=options.get("dry_run"),
        )
        try:
            self._run(options)
        except KeyboardInterrupt:
            self.stdout.write(
                "\n⚠️  Interrupted. All completed articles are safely saved."
            )
            logger.warning("generation_interrupted_by_user")
        except Exception as e:
            logger.error("generation_failed", error=str(e))
            sentry_sdk.capture_exception(e)
            raise CommandError(f"Generation failed: {e}")

    # ─────────────────────────────────────────────────────────────────────────

    def _run(self, options):
        subject_name = options.get("subject") or "Indian Polity & Constitution"
        single_topic = options.get("topic")
        dry_run = options.get("dry_run", False)
        max_topics = options.get("max_topics", 2)
        max_actual_articles = options.get("max_actual_articles", 15)
        max_subtopics_per_topic = options.get("max_subtopics_per_topic", 4)
        max_sub_subtopics = options.get("max_sub_subtopics_per_subtopic", 3)
        max_deep_per_topic = options.get("max_deep_per_topic", 2)

        # Shared mutable budget — passed by reference into every ingest_topic() call.
        # Decremented inside ingestor_service.py after each individual article is saved.
        # When it hits zero ingest_topic() raises BudgetExhaustedError and returns partial.
        budget = {"remaining": max_actual_articles}

        self.stdout.write("")
        self.stdout.write("╔══════════════════════════════════════════════════╗")
        self.stdout.write("║   🧪  TheKnowledgeOrbits — Book Content Engine   ║")
        self.stdout.write("║       3-Layer Quality Engine (GROQ free tier)    ║")
        self.stdout.write("╚══════════════════════════════════════════════════╝")
        self.stdout.write("")

        # ── Step 1: Verify DB state ───────────────────────────────────────────
        self.stdout.write("STEP 1: Verifying DB state...")
        self._verify_db_state()

        # ── Step 1.2: LLM pre-flight health check ────────────────────────────
        # Pings every key across every provider (GROQ + Cerebras).
        # Only aborts if ALL keys from ALL providers are simultaneously exhausted.
        if not dry_run:
            self.stdout.write("STEP 1.2: LLM pre-flight check (GROQ + Cerebras)...")
            if not check_any_llm_available():
                self.stdout.write(
                    self.style.WARNING(
                        "   ⚠️  All LLM providers exhausted (GROQ + Cerebras).\n"
                        "   Aborting to protect rate-limit budget. Try again after UTC midnight."
                    )
                )
                logger.warning("all_llm_preflight_failed_aborting")
                return  # Exit cleanly — no exception, no Sentry noise
            self.stdout.write(
                "   ✅ At least one LLM provider responding — proceeding with generation."
            )

        # ── Step 1.5: Book Intelligence Plan ─────────────────────────────────
        # For each subject being ingested, generate book plan first.
        modules = SUBJECT_MODULES.get(subject_name, [])
        existing_plan = get_book_plan(subject_name)

        if not existing_plan:
            if not dry_run:
                self.stdout.write(
                    f"\nSTEP 1.5: Generating Book Intelligence Plan for '{subject_name}'..."
                )
                generate_book_plan(subject_name, modules)
                self.stdout.write(
                    "   ✅ Book plan created. All subsequent articles will use it."
                )
            else:
                self.stdout.write(
                    f"\nSTEP 1.5: [DRY RUN] Would create book plan for '{subject_name}'"
                )
        else:
            self.stdout.write(
                f"\nSTEP 1.5: Book plan already exists for '{subject_name}' — skipping."
            )

        # ── Step 2A: Mode A — topic string ingestion ──────────────────────────
        topics = [single_topic] if single_topic else TOPICS_TO_GENERATE

        if topics:
            self.stdout.write("")
            self.stdout.write(
                f"STEP 2A: Ingesting {len(topics)} topic(s) [Mode A] — "
                f"topic cap: {max_topics}, article budget: {max_actual_articles}, "
                f"subtopics/topic: {max_subtopics_per_topic}"
            )

            topics_processed = 0

            for topic_name in topics:
                # ── Budget check: stop if article budget exhausted between topics ──
                if budget["remaining"] <= 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f"\n  🛑 Article budget exhausted ({max_actual_articles} articles done). "
                            "Stopping. Re-run to continue from next unfinished topic."
                        )
                    )
                    logger.info(
                        "article_budget_exhausted_between_topics",
                        budget=max_actual_articles,
                    )
                    break

                # ── Topic cap ────────────────────────────────────────────────────
                if topics_processed >= max_topics:
                    self.stdout.write(
                        self.style.WARNING(
                            f"\n  🛑 Topic cap reached ({max_topics}). "
                            "Remaining topics queued for next run."
                        )
                    )
                    logger.info("max_topics_cap_reached", cap=max_topics)
                    break

                # Only skip if the ENTIRE topic is fully complete (content_status='book_quality').
                # Partial runs (topic overview saved but subtopics not done) must NOT be skipped
                # here — ingestor_service.py handles per-subtopic smart-skip internally.
                fully_done = Topic.objects.filter(
                    name=topic_name,
                    content_status="book_quality",
                ).exists()

                if fully_done:
                    self.stdout.write(
                        f"  ⏭️  Skipping '{topic_name}' — fully generated (book_quality)"
                    )
                    continue

                if dry_run:
                    self.stdout.write(f"  [DRY RUN] Would generate: '{topic_name}'")
                    continue

                # ── Between-topic LLM health check ───────────────────────────────
                # A cheap sanity check before we start a new topic.
                # The real circuit breaker is now INSIDE ingest_topic() every 3 subtopics.
                if topics_processed > 0:
                    self.stdout.write(f"  🔍 LLM health check before '{topic_name}'...")
                    if not check_any_llm_available():
                        self.stdout.write(
                            self.style.WARNING(
                                "  ⚠️  All LLM providers exhausted between topics.\n"
                                "  🛑 Aborting — re-run after UTC midnight to resume."
                            )
                        )
                        logger.warning(
                            "all_llm_exhausted_between_topics",
                            topics_processed=topics_processed,
                        )
                        break

                self.stdout.write(
                    f"\n  🔄 Generating: '{topic_name}' "
                    f"(budget left: {budget['remaining']}/{max_actual_articles})..."
                )
                result = ingest_topic(
                    topic_name=topic_name,
                    subject_name=subject_name,
                    budget=budget,
                    max_subtopics=max_subtopics_per_topic,
                    max_sub_subtopics=max_sub_subtopics,
                    max_deep_per_topic=max_deep_per_topic,
                )
                topics_processed += 1

                status_tag = "partial" if result.get("partial") else "done"
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✅ '{topic_name}' {status_tag} — "
                        f"{result.get('nodes_created', 0)} articles  "
                        f"[topics: {topics_processed}/{max_topics}  "
                        f"budget left: {budget['remaining']}/{max_actual_articles}]"
                    )
                )

                # If ingest_topic returned partial (budget hit zero inside), stop now.
                if result.get("partial"):
                    self.stdout.write(
                        self.style.WARNING(
                            "  🛑 Budget exhausted mid-topic. All progress saved. "
                            "Re-run to continue."
                        )
                    )
                    logger.info(
                        "budget_exhausted_mid_topic_outer_loop",
                        topic=topic_name,
                        reason=result.get("reason", ""),
                    )
                    break

        # ── Step 2B: Mode B — PDF ingestion (future feature) ─────────────────
        if PDF_MODE and PDF_FILES_TO_INGEST:
            self.stdout.write("")
            self.stdout.write(
                f"STEP 2B: Ingesting {len(PDF_FILES_TO_INGEST)} PDF(s) [Mode B]..."
            )
            self.stdout.write(
                "  ⚠️  PDF Mode is not yet implemented in the Django engine."
            )

        # ── Step 3: Full DB summary ───────────────────────────────────────────
        self._print_db_summary(subject_name)

        # ── Step 4: Launch instructions ───────────────────────────────────────
        self.stdout.write("")
        self.stdout.write("╔══════════════════════════════════════════════════╗")
        self.stdout.write("║         ✅  PIPELINE COMPLETE!                   ║")
        self.stdout.write("╠══════════════════════════════════════════════════╣")
        self.stdout.write("║                                                  ║")
        self.stdout.write("║  Launch the Django dev server:                   ║")
        self.stdout.write("║    python manage.py runserver                    ║")
        self.stdout.write("║                                                  ║")
        self.stdout.write("║  Then open: http://127.0.0.1:8000                ║")
        self.stdout.write("║                                                  ║")
        self.stdout.write("║  To generate more topics, edit TOPICS_TO_GENERATE║")
        self.stdout.write("║  in management/commands/generate_book_content.py ║")
        self.stdout.write("║                                                  ║")
        self.stdout.write("╚══════════════════════════════════════════════════╝")
        self.stdout.write("")

    def _verify_db_state(self):
        """
        Verifies all required tables exist.
        Equivalent to POC's build_schema() — but Django migrations handle this.
        """
        try:
            # Check core tables via ORM (will raise if missing)
            _ = BookContent.objects.count()
            _ = GenerationLog.objects.count()
            _ = Topic.objects.count()
            self.stdout.write("   ✅ DB tables verified — all present.")
        except Exception as e:
            logger.error("db_verification_failed", error=str(e))
            sentry_sdk.capture_exception(e)
            raise CommandError(
                f"DB verification failed: {e}\n" "Run: python manage.py migrate"
            )

    def _print_db_summary(self, subject_name: str):
        """
        Prints a full summary of what's in the database after ingestion.
        Django ORM equivalent of POC's print_db_summary() (raw SQL → ORM).
        """
        self.stdout.write("")
        self.stdout.write("━" * 55)
        self.stdout.write("📊 DATABASE SUMMARY")
        self.stdout.write("━" * 55)

        # ── Overall counts ────────────────────────────────────────────────────
        total_articles = BookContent.objects.filter(subject__name=subject_name).count()
        total_words = sum(
            bc.word_count
            for bc in BookContent.objects.filter(subject__name=subject_name)
        )
        quality_scores = list(
            BookContent.objects.filter(
                subject__name=subject_name,
                quality_score__gt=0,
            ).values_list("quality_score", flat=True)
        )
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0

        self.stdout.write(f"  Total Articles : {total_articles}")
        self.stdout.write(f"  Total Words    : {total_words:,} words of content")
        self.stdout.write(
            f"  Est. Pages     : ~{total_words // 300} pages (at 300 words/page)"
        )
        self.stdout.write(
            f"  Avg Quality    : {avg_quality:.1f} / 100 (3-Layer Engine)"
        )

        # ── Articles by node type ─────────────────────────────────────────────
        self.stdout.write("")
        self.stdout.write("  Articles by node type:")

        node_type_icons = {
            "subject_root": "📚",
            "module": "📂",
            "topic": "📄",
            "subtopic": "🔹",
            "sub_subtopic": "▸",
        }
        for node_type, icon in node_type_icons.items():
            qs = BookContent.objects.filter(
                subject__name=subject_name,
                topic__node_type=node_type,
            )
            count = qs.count()
            if count == 0:
                continue
            words = sum(bc.word_count for bc in qs)
            self.stdout.write(
                f"    {icon}  {node_type:<14}: {count:>3} articles | {words:>8,} words"
            )

        # ── Full hierarchy with word counts ───────────────────────────────────
        self.stdout.write("")
        self.stdout.write("  Full Hierarchy (with word counts):")

        # Subjects
        for subject in Subject.objects.filter(name=subject_name):
            self.stdout.write(f"    📚 {subject.name}")

            # Modules (topics with no parent)
            for module_topic in Topic.objects.filter(
                subject=subject,
                parent_topic__isnull=True,
                node_type__in=["module", "topic"],
            ).order_by("order_index"):
                bc = BookContent.objects.filter(topic=module_topic).first()
                wc_str = f"{bc.word_count:,} words" if bc and bc.word_count > 0 else ""
                icon = "📂" if module_topic.node_type == "module" else "📄"
                self.stdout.write(f"      {icon} {module_topic.name}  {wc_str}")

                # Subtopics
                for subtopic in Topic.objects.filter(
                    parent_topic=module_topic,
                ).order_by("order_index"):
                    sub_bc = BookContent.objects.filter(topic=subtopic).first()
                    sub_wc = (
                        f"{sub_bc.word_count:,} words"
                        if sub_bc and sub_bc.word_count > 0
                        else ""
                    )
                    sub_icon = {"subtopic": "🔹", "sub_subtopic": "▸"}.get(
                        subtopic.node_type, "🔹"
                    )
                    self.stdout.write(f"        {sub_icon} {subtopic.name}  {sub_wc}")

        # ── Recent ingestion logs ─────────────────────────────────────────────
        self.stdout.write("")
        self.stdout.write("  Recent ingestion logs:")

        recent_logs = GenerationLog.objects.filter(
            subject_name=subject_name,
        ).order_by("-created_at")[:5]

        if recent_logs:
            for log in recent_logs:
                icon = "✅" if log.status == "success" else "❌"
                self.stdout.write(
                    f"    {icon} {log.topic_name}  →  "
                    f"{log.nodes_created} articles  ({log.created_at:%Y-%m-%d %H:%M})"
                )
        else:
            self.stdout.write("    (no logs yet)")

        self.stdout.write("")
