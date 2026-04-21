"""
Migration 0004 — Search: GIN trigram indexes on ca_article.title + summary

Problem:
  _ca_article_search() in search_service.py fires:
      CAArticle.objects.filter(Q(title__icontains=query) | Q(summary__icontains=query))
  Both fields use LIKE '%query%' with no trigram index → sequential scan on
  ca_article table on every search request.

Fix:
  GIN trigram indexes on title and summary columns.
  pg_trgm already enabled via book_content migration 0005.

atomic = False required: CREATE INDEX CONCURRENTLY cannot run in a transaction.
Expected improvement: 100–200ms → <5ms on CA article keyword fallback.
"""

from django.db import migrations


class Migration(migrations.Migration):
    atomic = False  # CONCURRENTLY cannot run inside a transaction

    dependencies = [
        ("current_affairs", "0003_caarticle_ca_article_source__547539_idx"),
    ]

    operations = [
        # pg_trgm already enabled — idempotent guard
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS pg_trgm;",
            reverse_sql="-- pg_trgm intentionally left installed on rollback.",
        ),
        # GIN trigram index on ca_article.title
        # Accelerates: CAArticle.objects.filter(title__icontains="...")
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS ca_article_title_trgm_idx
                ON ca_article
                USING gin (title gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS ca_article_title_trgm_idx;",
        ),
        # GIN trigram index on ca_article.summary
        # Accelerates: CAArticle.objects.filter(summary__icontains="...")
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS ca_article_summary_trgm_idx
                ON ca_article
                USING gin (summary gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS ca_article_summary_trgm_idx;",
        ),
    ]
