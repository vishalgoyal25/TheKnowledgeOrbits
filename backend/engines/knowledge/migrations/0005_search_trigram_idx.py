"""
Migration 0005 — Search: GIN trigram indexes on knowledge_topic.name + description

Problem:
  _topic_search() in search_service.py fires:
      Topic.objects.filter(Q(name__icontains=query) | Q(description__icontains=query))
  Both fields use LIKE '%query%' with no trigram index → sequential scan on
  knowledge_topic table on every search request.

Fix:
  GIN trigram indexes on name and description columns.
  pg_trgm already enabled via book_content migration 0005.

atomic = False required: CREATE INDEX CONCURRENTLY cannot run in a transaction.
Expected improvement: 100–200ms → <5ms on topic keyword fallback.
"""

from django.db import migrations


class Migration(migrations.Migration):
    atomic = False  # CONCURRENTLY cannot run inside a transaction

    dependencies = [
        ("knowledge", "0004_topic_add_content_status_squashed"),
    ]

    operations = [
        # pg_trgm already enabled — idempotent guard
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS pg_trgm;",
            reverse_sql="-- pg_trgm intentionally left installed on rollback.",
        ),
        # GIN trigram index on knowledge_topic.name
        # Accelerates: Topic.objects.filter(name__icontains="...")
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS knowledge_topic_name_trgm_idx
                ON knowledge_topic
                USING gin (name gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS knowledge_topic_name_trgm_idx;",
        ),
        # GIN trigram index on knowledge_topic.description
        # Accelerates: Topic.objects.filter(description__icontains="...")
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS knowledge_topic_desc_trgm_idx
                ON knowledge_topic
                USING gin (description gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS knowledge_topic_desc_trgm_idx;",
        ),
    ]
