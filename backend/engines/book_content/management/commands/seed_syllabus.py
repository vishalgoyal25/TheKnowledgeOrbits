"""
backend/engines/book_content/management/commands/seed_syllabus.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase F — UPSC Syllabus Seed Command

Seeds the complete UPSC CSE syllabus hierarchy into the knowledge_* tables.

Hierarchy:
  Program (UPSC CSE)
    └── Subject        (e.g. "Indian Polity & Constitution")
          └── Module   (e.g. "Fundamental Rights & Duties")
                └── Topic        (e.g. "Right to Equality")
                      └── Subtopic     (e.g. "Article 14 — Equality Before Law")
                            └── Sub-subtopic (e.g. "Reasonable Classification Doctrine")

Usage:
  # Seed everything (safe to re-run — fully idempotent via get_or_create)
  python manage.py seed_syllabus

  # Seed only one subject (for testing / incremental addition)
  python manage.py seed_syllabus --subject "Indian Polity & Constitution"

  # Dry-run: print what would be created without touching the DB
  python manage.py seed_syllabus --dry-run

Design rules:
  - get_or_create at EVERY level → 100% idempotent, re-run anytime
  - order_index preserved from SYLLABUS dict ordering → stable sort
  - node_type set correctly at every level for KnowledgeGraph rendering
  - is_active=True on all nodes so they appear in hamburger/navbar/graph
  - NO deletion — only addition. Removing a subject requires manual DB action.
  - Prints a summary after each subject: modules, topics, subtopics created
  - Works on local PostgreSQL and Supabase (same schema)

Adding new subjects:
  Just add a new key to SYLLABUS dict below and re-run the command.
  Existing records are untouched (get_or_create). Zero risk.

Structure of SYLLABUS dict:
  {
    "Subject Name": {
      "Module Name": {
        "Topic Name": {
          "Subtopic Name": [
            "Sub-subtopic A",
            "Sub-subtopic B",
            ...
          ],
          ...
        },
        ...
      },
      ...
    },
    ...
  }

  If a topic has NO subtopics → use an empty dict {}
  If a subtopic has NO sub-subtopics → use an empty list []
"""

import structlog
from django.core.management.base import BaseCommand
from django.db import transaction

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# SYLLABUS DATA
# Subjects are added one by one as user provides and verifies each.
# Format: { Subject: { Module: { Topic: { Subtopic: [Sub-subtopics] } } } }
# ═══════════════════════════════════════════════════════════════════════════════

SYLLABUS: dict = {
    "Indian Polity & Constitution": {
        "Constitutional Framework": {
            "Preamble to the Constitution of India": {
                "Meaning and Significance of Preamble": [],
                "Key Words in Preamble": [],
                "Preamble and Basic Structure Doctrine": [],
                "42nd Amendment and Preamble": [],
            },
            "Making of the Indian Constitution": {
                "Constituent Assembly": [],
                "Sources of Indian Constitution": [],
            },
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# MANAGEMENT COMMAND
# ═══════════════════════════════════════════════════════════════════════════════


class Command(BaseCommand):
    help = (
        "Seeds the complete UPSC CSE syllabus hierarchy into knowledge_* tables. "
        "Fully idempotent — safe to re-run at any time."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--subject",
            type=str,
            default=None,
            help="Seed only this subject (exact name). Omit to seed all subjects.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Print what would be created without writing to the database.",
        )

    def handle(self, *args, **options):
        target_subject = options.get("subject")
        dry_run = options.get("dry_run")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no database writes.\n"))

        if not SYLLABUS:
            self.stdout.write(
                self.style.WARNING(
                    "SYLLABUS dict is empty. "
                    "Add subject data before running this command."
                )
            )
            return

        subjects_to_seed = (
            {target_subject: SYLLABUS[target_subject]}
            if target_subject and target_subject in SYLLABUS
            else SYLLABUS
        )

        if target_subject and target_subject not in SYLLABUS:
            self.stdout.write(
                self.style.ERROR(f"Subject '{target_subject}' not found in SYLLABUS.")
            )
            return

        # Ensure UPSC CSE program exists
        program = self._get_or_create_program(dry_run)

        total_subjects = total_modules = total_topics = 0
        total_subtopics = total_sub_subtopics = 0

        for subject_name, modules in subjects_to_seed.items():
            counts = self._seed_subject(subject_name, modules, program, dry_run)
            total_subjects += 1
            total_modules += counts["modules"]
            total_topics += counts["topics"]
            total_subtopics += counts["subtopics"]
            total_sub_subtopics += counts["sub_subtopics"]

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'[DRY RUN] ' if dry_run else ''}Seeding complete!\n"
                f"  Subjects      : {total_subjects}\n"
                f"  Modules       : {total_modules}\n"
                f"  Topics        : {total_topics}\n"
                f"  Subtopics     : {total_subtopics}\n"
                f"  Sub-subtopics : {total_sub_subtopics}\n"
                f"  TOTAL NODES   : {total_subjects + total_modules + total_topics + total_subtopics + total_sub_subtopics}"
            )
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # SEEDING HELPERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _get_or_create_program(self, dry_run: bool):
        if dry_run:
            return None
        from engines.knowledge.models import Program

        program, created = Program.objects.get_or_create(
            name="UPSC CSE",
            defaults={"description": "UPSC Civil Services Examination"},
        )
        if created:
            self.stdout.write("  Created Program: UPSC CSE")
        return program

    def _seed_subject(
        self, subject_name: str, modules: dict, program, dry_run: bool
    ) -> dict:
        from engines.knowledge.models import Module, Subject, Topic

        counts = {"modules": 0, "topics": 0, "subtopics": 0, "sub_subtopics": 0}

        self.stdout.write(f"\nSeeding Subject: {subject_name}")

        if dry_run:
            for module_name, topics in modules.items():
                self.stdout.write(f"  [DRY] Module: {module_name}")
                counts["modules"] += 1
                for topic_name, subtopics in topics.items():
                    self.stdout.write(f"    [DRY] Topic: {topic_name}")
                    counts["topics"] += 1
                    for subtopic_name, sub_subtopics in subtopics.items():
                        self.stdout.write(f"      [DRY] Subtopic: {subtopic_name}")
                        counts["subtopics"] += 1
                        for ss_name in sub_subtopics:
                            self.stdout.write(f"        [DRY] Sub-subtopic: {ss_name}")
                            counts["sub_subtopics"] += 1
            return counts

        with transaction.atomic():
            # ── Subject ───────────────────────────────────────────────────────
            subject_obj, s_created = Subject.objects.get_or_create(
                name=subject_name,
                program=program,
                defaults={
                    "description": f"UPSC CSE subject: {subject_name}",
                    "is_active": True,
                },
            )

            for mod_idx, (module_name, topics) in enumerate(modules.items()):
                # ── Module ────────────────────────────────────────────────────
                module_obj, m_created = Module.objects.get_or_create(
                    name=module_name,
                    subject=subject_obj,
                    defaults={
                        "description": f"{module_name}",
                        "is_active": True,
                        "order_index": mod_idx,
                    },
                )
                counts["modules"] += 1

                for top_idx, (topic_name, subtopics) in enumerate(topics.items()):
                    # ── Topic ─────────────────────────────────────────────────
                    topic_obj, t_created = Topic.objects.get_or_create(
                        name=topic_name,
                        module=module_obj,
                        defaults={
                            "subject": subject_obj,
                            "is_active": True,
                            "topic_type": "syllabus",
                            "order_index": top_idx,
                        },
                    )
                    if t_created:
                        Topic.objects.filter(id=topic_obj.id).update(node_type="topic")
                    counts["topics"] += 1

                    for sub_idx, (subtopic_name, sub_subtopics) in enumerate(
                        subtopics.items()
                    ):
                        # ── Subtopic ──────────────────────────────────────────
                        subtopic_obj, st_created = Topic.objects.get_or_create(
                            name=subtopic_name,
                            module=module_obj,
                            defaults={
                                "subject": subject_obj,
                                "parent_topic": topic_obj,
                                "is_active": True,
                                "topic_type": "syllabus",
                                "order_index": sub_idx,
                            },
                        )
                        if st_created:
                            Topic.objects.filter(id=subtopic_obj.id).update(
                                node_type="subtopic"
                            )
                        counts["subtopics"] += 1

                        for ss_idx, ss_name in enumerate(sub_subtopics):
                            # ── Sub-subtopic ──────────────────────────────────
                            ss_obj, ss_created = Topic.objects.get_or_create(
                                name=ss_name,
                                module=module_obj,
                                defaults={
                                    "subject": subject_obj,
                                    "parent_topic": subtopic_obj,
                                    "is_active": True,
                                    "topic_type": "syllabus",
                                    "order_index": ss_idx,
                                },
                            )
                            if ss_created:
                                Topic.objects.filter(id=ss_obj.id).update(
                                    node_type="sub_subtopic"
                                )
                            counts["sub_subtopics"] += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"  ✅ {subject_name}: "
                f"{counts['modules']} modules, "
                f"{counts['topics']} topics, "
                f"{counts['subtopics']} subtopics, "
                f"{counts['sub_subtopics']} sub-subtopics"
            )
        )
        logger.info(
            "seed_syllabus_subject_complete",
            subject=subject_name,
            **counts,
        )
        return counts
