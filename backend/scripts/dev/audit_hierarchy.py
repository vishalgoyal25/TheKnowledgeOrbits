"""
scripts/dev/audit_hierarchy.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Is there ONE syllabus hierarchy in the database, or two seeded on top of each other?

WHY (2026-09-15)
  Two seed commands exist — knowledge/seed_upsc_syllabus.py (older, program
  "UPSC Civil Services Examination", flat topics, deletes ALL programs first)
  and book_content/seed_syllabus.py (newer, program "UPSC CSE", nested
  topic > subtopic > sub_subtopic with node_type). The /subjects, /modules and
  /topics pages and the /knowledge map read the SAME three tables, yet the
  developer sees two different trees. This prints what is actually there, so
  the clean-up is designed against facts, not memory.

WHAT IT PRINTS (read-only)
  programs           each program with subject/module/topic counts
  seed fingerprints  topics grouped by created_at DATE and node_type — two seed
                     runs show as two clusters; the description prefix tells
                     which seed wrote a subject
  shape              root topics (parent NULL) by node_type; subtopic-typed
                     rows with NO parent (orphans of a flattened seed); modules
                     with zero topics; topics with no module/subject agreement
  content            topics with BookContent (map articles) vs with generated
                     Article rows (page articles) vs neither
  per subject        modules and root-topic counts, so the two UIs can be
                     compared line by line

USAGE (from backend/, venv active)
      python scripts/dev/audit_hierarchy.py --database=supabase
      python scripts/dev/audit_hierarchy.py --database=supabase > scripts/dev/audit_hierarchy_report.txt

SAFETY
  Read-only. Nothing is written.
"""

import argparse
import os
import sys
from collections import Counter, defaultdict

import django

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.dev")
django.setup()

from django.db.models import Count  # noqa: E402

from engines.knowledge.models import Module, Program, Subject, Topic  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default="default", help="DB alias")
    args = parser.parse_args()
    db = args.database

    print(f"\n{'=' * 72}\nHierarchy audit — database '{db}'\n{'=' * 72}")

    # ── Programs ──────────────────────────────────────────────────────────
    print("\nPROGRAMS")
    for p in Program.objects.using(db).order_by("created_at"):
        n_s = Subject.objects.using(db).filter(program=p).count()
        n_m = Module.objects.using(db).filter(subject__program=p).count()
        n_t = Topic.objects.using(db).filter(subject__program=p).count()
        print(
            f"  {p.name!r:<45} created {p.created_at:%Y-%m-%d}  "
            f"subjects={n_s} modules={n_m} topics={n_t} active={p.is_active}"
        )

    # ── Seed fingerprints ─────────────────────────────────────────────────
    print("\nSEED FINGERPRINTS — topics by created_at date × node_type")
    by_day: dict = defaultdict(Counter)
    for created, node_type in Topic.objects.using(db).values_list(
        "created_at", "node_type"
    ):
        by_day[created.date()][node_type] += 1
    for day in sorted(by_day):
        parts = ", ".join(f"{k}={v}" for k, v in sorted(by_day[day].items()))
        print(f"  {day}  total={sum(by_day[day].values()):>5}  {parts}")

    print("\n  subject description prefixes (which seed wrote the subject):")
    prefixes = Counter(
        (d or "")[:24]
        for d in Subject.objects.using(db).values_list("description", flat=True)
    )
    for prefix, n in prefixes.most_common():
        print(f"    {n:>3}  {prefix!r}")

    # ── Shape ─────────────────────────────────────────────────────────────
    print("\nSHAPE")
    roots = Counter(
        Topic.objects.using(db)
        .filter(parent_topic__isnull=True)
        .values_list("node_type", flat=True)
    )
    print(f"  root topics (parent NULL) by node_type: {dict(roots)}")
    orphan_subs = (
        Topic.objects.using(db)
        .filter(parent_topic__isnull=True, node_type__in=["subtopic", "sub_subtopic"])
        .count()
    )
    print(f"  subtopic-typed rows with NO parent (flattened seed): {orphan_subs}")
    typed_topic_with_parent = (
        Topic.objects.using(db)
        .filter(parent_topic__isnull=False, node_type="topic")
        .count()
    )
    print(
        f"  'topic'-typed rows that HAVE a parent (mis-typed): {typed_topic_with_parent}"
    )
    empty_modules = (
        Module.objects.using(db).annotate(n=Count("topics")).filter(n=0).count()
    )
    print(f"  modules with zero topics: {empty_modules}")
    bad = sum(
        1
        for t in Topic.objects.using(db).select_related("module")
        if t.module.subject_id != t.subject_id
    )
    print(f"  topics whose subject_id != module.subject_id: {bad}")
    inactive = Topic.objects.using(db).filter(is_active=False).count()
    print(f"  inactive topics: {inactive}")

    # ── Content ───────────────────────────────────────────────────────────
    print("\nCONTENT — which system has written to which topics")
    qs = Topic.objects.using(db).annotate(
        n_book=Count("book_content", distinct=True),
        n_art=Count("articles", distinct=True),
    )
    total = qs.count()
    with_book = qs.filter(n_book__gt=0).count()
    with_art = qs.filter(n_art__gt=0).count()
    both = qs.filter(n_book__gt=0, n_art__gt=0).count()
    neither = qs.filter(n_book=0, n_art=0).count()
    print(f"  topics total                         {total}")
    print(f"  with BookContent (map article)       {with_book}")
    print(f"  with generated Article (page list)   {with_art}")
    print(f"  with both                            {both}")
    print(f"  with neither                         {neither}")
    status = Counter(Topic.objects.using(db).values_list("content_status", flat=True))
    print(f"  content_status: {dict(status)}")

    # ── Per subject ───────────────────────────────────────────────────────
    print("\nPER SUBJECT — modules · root topics · all topics · with map article")
    for s in (
        Subject.objects.using(db)
        .select_related("program")
        .order_by("program", "order_index", "name")
    ):
        mods = (
            Module.objects.using(db).filter(subject=s).order_by("order_index", "name")
        )
        print(f"\n  [{s.program.name}] {s.name}  ({s.slug})")
        for m in mods:
            all_t = Topic.objects.using(db).filter(module=m)
            root_t = all_t.filter(parent_topic__isnull=True)
            with_book = all_t.filter(book_content__isnull=False).count()
            print(
                f"      {m.name:<48} roots={root_t.count():>3} all={all_t.count():>3} "
                f"book={with_book:>3}  ({m.slug})"
            )
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
