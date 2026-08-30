"""
scripts/dev/supabase_backup.py — S2 safety net for FEATURES_SUPABASE_CLEANUP.md

Exports every table we intend to KEEP to CSV, before any destructive DELETE.

WHY THIS EXISTS
Supabase free tier has NO point-in-time recovery and NO restore. Once S3/S4 delete
rows there is no undo. This script is the only thing standing between a mistyped
WHERE clause and permanent loss of the static syllabus corpus.

DESIGN NOTES
  • Driver-agnostic: plain SELECT + csv writer, so it works on psycopg2 or psycopg3
    (this project has both installed). No COPY, no pg_dump, no PATH assumptions.
  • Streams in batches — never loads a whole table into memory.
  • content_embedding is exported FILTERED (content_type <> 'ca_chunk'). Dumping all
    232k rows would write ~600 MB of vectors that we are about to delete anyway.
  • Credentials come from Django settings (SB_DB_* in .env). Nothing is printed.

Output: backups/supabase_keep_<UTC timestamp>/<table>.csv  (+ MANIFEST.txt)
`backups/` MUST be gitignored — these CSVs contain real content.

Run:  python scripts/dev/supabase_backup.py
"""

from __future__ import annotations

import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.dev")
django.setup()

from django.db import connections  # noqa: E402

BATCH = 2_000

# Tables to preserve. Anything not listed is either regenerable (CA content) or
# about to be deleted on purpose.
TABLES: list[tuple[str, str]] = [
    # ── Static syllabus corpus — THE irreplaceable asset ──────────────────
    ("knowledge_book_chunk", "SELECT * FROM knowledge_book_chunk"),
    ("knowledge_book_content", "SELECT * FROM knowledge_book_content"),
    ("knowledge_topic", "SELECT * FROM knowledge_topic"),
    ("knowledge_subject", "SELECT * FROM knowledge_subject"),
    ("knowledge_module", "SELECT * FROM knowledge_module"),
    ("knowledge_program", "SELECT * FROM knowledge_program"),
    ("knowledge_theme", "SELECT * FROM knowledge_theme"),
    ("knowledge_topic_relation", "SELECT * FROM knowledge_topic_relation"),
    # ── Generated content worth keeping ───────────────────────────────────
    ("daily_ca_article", "SELECT * FROM daily_ca_article"),
    ("concept_page", "SELECT * FROM concept_page"),
    ("concept_article_link", "SELECT * FROM concept_article_link"),
    ("tag", "SELECT * FROM tag"),
    ("article_tag", "SELECT * FROM article_tag"),
    ("assessment_quiz", "SELECT * FROM assessment_quiz"),
    ("assessment_question", "SELECT * FROM assessment_question"),
    # ── Embeddings we KEEP (everything except the CA chunks being purged) ──
    (
        "content_embedding_keep",
        "SELECT * FROM content_embedding WHERE content_type <> 'ca_chunk'",
    ),
]


def export(cursor, name: str, sql: str, out_dir: Path) -> tuple[int, int]:
    """Stream one query to CSV. Returns (row_count, byte_size)."""
    cursor.execute(sql)
    headers = [c[0] for c in cursor.description]
    path = out_dir / f"{name}.csv"
    rows = 0

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        while True:
            batch = cursor.fetchmany(BATCH)
            if not batch:
                break
            writer.writerows(batch)
            rows += len(batch)
            print(f"    {name}: {rows:,} rows", end="\r", flush=True)

    return rows, path.stat().st_size


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    out_dir = (
        Path(__file__).resolve().parents[2].parent
        / "backups"
        / f"supabase_keep_{stamp}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("  S2 — SUPABASE BACKUP (tables to KEEP)")
    print(f"  → {out_dir}")
    print("=" * 70)

    manifest: list[str] = [f"Supabase KEEP backup — {stamp} UTC", ""]
    total_rows = total_bytes = 0
    failures: list[str] = []

    with connections["supabase"].cursor() as cursor:
        for name, sql in TABLES:
            try:
                rows, size = export(cursor, name, sql, out_dir)
                total_rows += rows
                total_bytes += size
                line = f"{name:<32} {rows:>9,} rows   {size / 1_048_576:>8.2f} MB"
                print(f"  ✓ {line}")
                manifest.append(line)
            except Exception as exc:
                msg = f"{name:<32} FAILED: {str(exc)[:120]}"
                print(f"  ✗ {msg}")
                manifest.append(msg)
                failures.append(name)

    manifest += [
        "",
        f"TOTAL {total_rows:,} rows, {total_bytes / 1_048_576:.2f} MB",
        f"failures: {failures or 'none'}",
    ]
    (out_dir / "MANIFEST.txt").write_text("\n".join(manifest), encoding="utf-8")

    print("=" * 70)
    print(f"  TOTAL: {total_rows:,} rows, {total_bytes / 1_048_576:.2f} MB")
    if failures:
        print(f"  ✗ GATE FAILED — {len(failures)} table(s) did not export: {failures}")
        print("  DO NOT PROCEED TO S3.")
        sys.exit(1)
    print("  ✓ S2 GATE PASSED — every KEEP table exported. Safe to proceed to S3.")
    print("=" * 70)


if __name__ == "__main__":
    main()
