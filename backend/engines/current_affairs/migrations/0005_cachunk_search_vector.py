"""
Migration 0005 — CAChunk: add precomputed search_vector + GIN index

Problem:
  _bm25_ca_chunk_search() in search_service.py currently computes tsvector
  on-the-fly for every search:

      sv = SearchVector("chunk_text", config="english")
      CAChunk.objects.annotate(sv=sv).filter(sv=search_q)

  This is a full sequential scan of ca_chunk on every request (50–200ms).
  BookChunk already has a precomputed search_vector + GIN index (<5ms).
  CAChunk needs the same treatment.

Fix:
  1. Add search_vector (tsvector) column to ca_chunk table.
  2. Create GIN index for sub-millisecond BM25 queries.
  3. Backfill all existing rows via UPDATE.

atomic = False required: CREATE INDEX CONCURRENTLY cannot run in a transaction.
Expected improvement: 50–200ms → <5ms on CA chunk BM25 search.

After this migration, search_service.py _bm25_ca_chunk_search() is updated to
use the precomputed field instead of on-the-fly computation.
"""

from django.db import migrations


class Migration(migrations.Migration):
    atomic = False  # CONCURRENTLY cannot run inside a transaction

    dependencies = [
        ("current_affairs", "0004_search_trigram_idx"),
    ]

    operations = [
        # Step 1 — Add search_vector column (nullable — backfilled in step 3).
        migrations.RunSQL(
            sql="""
                ALTER TABLE ca_chunk
                ADD COLUMN IF NOT EXISTS search_vector tsvector;
            """,
            reverse_sql="""
                ALTER TABLE ca_chunk
                DROP COLUMN IF EXISTS search_vector;
            """,
        ),
        # Step 2 — GIN index on search_vector (same as book_chunk_fts_idx).
        # CONCURRENTLY: zero table lock — safe on live production.
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS ca_chunk_search_vector_idx
                ON ca_chunk
                USING gin (search_vector);
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS ca_chunk_search_vector_idx;",
        ),
        # Step 3 — Backfill all existing rows.
        # New rows are populated via CAChunk.save() override.
        # Existing rows need a one-time UPDATE.
        migrations.RunSQL(
            sql="""
                UPDATE ca_chunk
                SET search_vector = to_tsvector('english', chunk_text)
                WHERE search_vector IS NULL AND chunk_text IS NOT NULL AND chunk_text <> '';
            """,
            reverse_sql="-- Backfill rollback not needed — column is dropped on reverse.",
        ),
    ]
