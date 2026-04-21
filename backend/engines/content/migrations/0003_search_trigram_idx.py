"""
Migration 0003 — Search: GIN trigram index on content_document.title

Problem:
  _keyword_chunk_search() in search_service.py fires:
      Chunk.objects.filter(document__title__icontains=query)
  This JOINs content_chunk → content_document and applies LIKE '%query%' on
  content_document.title. No trigram index exists → full sequential scan on
  every search request.

Fix:
  GIN trigram index on content_document.title using gin_trgm_ops.
  pg_trgm already enabled via book_content migration 0005 — just add the index.

atomic = False required: CREATE INDEX CONCURRENTLY cannot run in a transaction.
Expected improvement: 100–300ms → <10ms on title keyword fallback.
"""

from django.db import migrations


class Migration(migrations.Migration):
    atomic = False  # CONCURRENTLY cannot run inside a transaction

    dependencies = [
        ("content", "0002_alter_chunk_source_type_alter_document_source_type"),
    ]

    operations = [
        # pg_trgm already enabled — idempotent guard in case migration runs standalone
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS pg_trgm;",
            reverse_sql="-- pg_trgm intentionally left installed on rollback.",
        ),
        # GIN trigram index on content_document.title
        # Accelerates: Chunk.objects.filter(document__title__icontains="...")
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS content_document_title_trgm_idx
                ON content_document
                USING gin (title gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS content_document_title_trgm_idx;",
        ),
    ]
