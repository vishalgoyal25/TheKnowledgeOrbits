"""Measure today's database, so capacity figures stop being guesses.

Answers §19 item 7, open since 2026-09-28. Read-only.

🔴 Why one query has been blocking a whole capacity model
----------------------------------------------------------
Every number in `06_DESIGN.md` §2.3 is a **DELTA** -- "the Factory adds N rows".
Headroom is `limit - today - delta`, and `today` has never been measured. So the
plan can say what the Factory adds but not whether it fits.

The specific worry (§19 item 7): searching by MEANING stores 384 floats per
chunk, and Postgres builds an **HNSW index** over them which must fit in RAM or
every search falls back to disk.

    1M chunks x 384 floats x 4 bytes        ~= 1.5 GB of vectors
    + index overhead (A10: ~2.2x)           ~= 3.4 GB of RAM

**Three answers, two of them free:**
  1. a bigger Supabase plan (~$25/mo for 8 GB)
  2. 🟢 a PARTIAL index -- already planned in phase 2.8, scoped to the active
     processing_version, the 24-month window AND content_type='df_chunk'
  3. tiering: recent material indexed, older archived

🟢 So the mitigation exists. The unknown is only WHEN the line is crossed --
a SCHEDULE decision, never a redesign.

⚠️ Read-only by construction
-----------------------------
Every statement here is a SELECT against catalog views. Nothing is created,
altered or dropped. Safe to run against Supabase, which is why it accepts
`--database`.
"""

from pathlib import Path

import structlog
from django.core.management.base import BaseCommand
from django.db import connections

logger = structlog.get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[5]

# 06_DESIGN.md A10: one 384-dim vector plus its share of the HNSW index.
KB_PER_VECTOR = 3.4

# Phase 2.8's alarm threshold for the partial index.
INDEX_ALARM_MB = 800


class Command(BaseCommand):
    help = (
        "Report current database size, row counts and index sizes so the "
        "capacity model has a baseline. Read-only."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            default="default",
            help="Which connection. Use 'supabase' for the real baseline.",
        )

    def handle(self, *args, **options):
        alias = options["database"]
        self.stdout.write(
            self.style.MIGRATE_HEADING(f"\n  DATABASE BASELINE — '{alias}'\n")
        )

        with connections[alias].cursor() as cur:
            cur.execute(
                "SELECT current_database(), pg_database_size(current_database())"
            )
            name, size_bytes = cur.fetchone()
            size_mb = size_bytes / 1_048_576

            self.stdout.write(f"  database              {name}")
            self.stdout.write(
                self.style.SUCCESS(f"  total size            {size_mb:,.1f} MB")
            )

            # The vector table is the one that decides the memory question.
            embedding_rows = self._count(cur, "content_embedding")
            self.stdout.write("")
            self.stdout.write(
                self.style.SUCCESS(
                    f"  🔴 content_embedding   {embedding_rows:,} vectors"
                )
            )
            if embedding_rows:
                implied_mb = embedding_rows * KB_PER_VECTOR / 1024
                self.stdout.write(
                    f"     implied index         ~{implied_mb:,.0f} MB "
                    f"(A10: {KB_PER_VECTOR} KB/vector incl. index)"
                )

            # Chunk tables, because the Factory adds a THIRD family to them.
            self.stdout.write("\n  Chunk families (all feed content_embedding):")
            for table in ("content_chunk", "ca_chunk", "book_chunk", "df_chunk"):
                self.stdout.write(f"    {table:<18} {self._count(cur, table):>10,}")

            self.stdout.write("\n  Data Factory tables:")
            for table in ("df_source", "df_artifact", "df_chunk", "df_atom"):
                self.stdout.write(f"    {table:<18} {self._count(cur, table):>10,}")

            # Largest tables and indexes, to see where the space actually went.
            self.stdout.write("\n  Ten largest relations:")
            cur.execute(
                """
                SELECT relname,
                       pg_total_relation_size(c.oid) AS total
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind = 'r'
                ORDER BY total DESC
                LIMIT 10
                """
            )
            for relname, total in cur.fetchall():
                self.stdout.write(f"    {relname:<34} {total / 1_048_576:>8,.1f} MB")

            self.stdout.write("\n  Vector indexes (the ones that must fit in RAM):")
            cur.execute(
                """
                SELECT indexrelname,
                       pg_relation_size(indexrelid) AS sz
                FROM pg_stat_user_indexes
                WHERE indexrelname ILIKE '%embed%' OR indexrelname ILIKE '%hnsw%'
                ORDER BY sz DESC
                """
            )
            rows = cur.fetchall()
            if not rows:
                self.stdout.write("    (none found — no HNSW index built yet)")
            for indexrelname, sz in rows:
                mb = sz / 1_048_576
                marker = "  ⚠️ OVER ALARM" if mb > INDEX_ALARM_MB else ""
                self.stdout.write(f"    {indexrelname:<34} {mb:>8,.1f} MB{marker}")

            table_count = self._scalar(
                cur,
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = 'public'",
            )
            self.stdout.write(f"\n  tables in public      {table_count}")

        # 🔴 The headroom reading, stated in words so §19 item 7 is answered
        # rather than merely measured.
        self.stdout.write("\n" + "=" * 62)
        if embedding_rows < 100_000:
            self.stdout.write(
                self.style.SUCCESS(
                    "  🟢 PLENTY OF HEADROOM. Under 100k vectors today, and the plan\n"
                    "     adds ~420k chunks by month 24. The partial index of phase 2.8\n"
                    "     is a precaution, not an urgent need."
                )
            )
        elif embedding_rows < 500_000:
            self.stdout.write(
                self.style.WARNING(
                    "  🟡 BUILD THE PARTIAL INDEX IN 2.8 AS PLANNED. Already a\n"
                    "     meaningful base; the Factory's additions will matter."
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    "  🔴 TIERING NEEDED EARLY. Over 500k vectors before the Factory\n"
                    "     adds any. Decide between a larger Supabase plan and archiving\n"
                    "     cold chunks BEFORE phase 2.8, not after."
                )
            )
        self.stdout.write("=" * 62)
        self.stdout.write(
            "\n  ⚠️ Run with --database=supabase for the figure that actually counts."
        )

        logger.info(
            "df_db_baseline",
            alias=alias,
            size_mb=round(size_mb, 1),
            embedding_rows=embedding_rows,
            tables=table_count,
        )

    # ── helpers ────────────────────────────────────────────────────────────

    def _count(self, cur, table: str) -> int:
        """Exact count, or 0 when the table does not exist on this connection."""
        try:
            cur.execute(f"SELECT count(*) FROM {table}")  # noqa: S608 - fixed names
            return int(cur.fetchone()[0])
        except Exception:  # noqa: BLE001 - a missing table is an answer, not an error
            return 0

    def _scalar(self, cur, sql: str) -> int:
        cur.execute(sql)
        return int(cur.fetchone()[0])
