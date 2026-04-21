"""
Migration 0006 — Search: GIN trigram indexes on daily_ca_article.title + news_context

Problem:
  DailyCaArticle (Feature 2 — /daily-ca/) is completely absent from global search.
  Adding keyword search requires LIKE '%query%' on title and news_context.
  Without trigram indexes, these fire sequential scans on the full table.

Fix:
  GIN trigram indexes on daily_ca_article.title and daily_ca_article.news_context.
  pg_trgm already enabled via book_content migration 0005.

  search_service.py _daily_ca_article_search() uses these to find published
  Daily CA articles by title and news context match.

atomic = False required: CREATE INDEX CONCURRENTLY cannot run in a transaction.
Expected improvement: sequential scan → <5ms on title/news_context keyword search.
"""

from django.db import migrations


class Migration(migrations.Migration):
    atomic = False  # CONCURRENTLY cannot run inside a transaction

    dependencies = [
        ("daily_ca", "0005_p14_compound_indexes"),
    ]

    operations = [
        # pg_trgm already enabled — idempotent guard
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS pg_trgm;",
            reverse_sql="-- pg_trgm intentionally left installed on rollback.",
        ),
        # GIN trigram index on daily_ca_article.title
        # Accelerates: DailyCaArticle.objects.filter(title__icontains="...")
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS daily_ca_article_title_trgm_idx
                ON daily_ca_article
                USING gin (title gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS daily_ca_article_title_trgm_idx;",
        ),
        # GIN trigram index on daily_ca_article.news_context
        # Accelerates: DailyCaArticle.objects.filter(news_context__icontains="...")
        # news_context = 3-sentence news summary — highly searchable for current events
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS daily_ca_article_news_context_trgm_idx
                ON daily_ca_article
                USING gin (news_context gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS daily_ca_article_news_context_trgm_idx;",
        ),
    ]
