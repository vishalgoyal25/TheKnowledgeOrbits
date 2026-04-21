"""
Migration 0005 — P3.6 Trigram (GIN) indexes for GenerationLog icontains search.

Problem:
  GenerationLog.subject_name and topic_name are used with __icontains filters in
  the admin GenerationLogView (book_content/views.py ~line 459). ILIKE '%...%'
  queries cannot use a regular B-tree index — the existing gen_log_subject_idx and
  gen_log_topic_idx on these fields do nothing for ILIKE. PostgreSQL falls back to
  a full sequential scan on every admin search.

Fix:
  1. Enable the pg_trgm extension (safe — idempotent IF NOT EXISTS, admin privilege
     on Supabase is already present).
  2. Add two GIN trigram indexes via RunSQL. GIN + gin_trgm_ops is the only index
     type that accelerates LIKE/ILIKE '%...%' on text columns.

Why atomic = False:
  CREATE INDEX CONCURRENTLY cannot run inside a transaction. Setting atomic=False
  makes this migration run outside Django's default transaction wrapper.
  CONCURRENTLY means zero table lock — safe to run on a live production database.

No model change needed:
  Django's query planner uses these indexes automatically. The model Meta.indexes
  list does not need to declare them (that requires django.contrib.postgres which
  is not in INSTALLED_APPS). The indexes are invisible to Django's ORM state but
  are fully active on the PostgreSQL side.
"""

from django.db import migrations


class Migration(migrations.Migration):
    # CONCURRENTLY cannot run inside a transaction — required for this migration.
    atomic = False

    dependencies = [
        ("book_content", "0004_p14_compound_indexes"),
    ]

    operations = [
        # Step 1 — Enable pg_trgm extension (idempotent, superuser on Supabase has this).
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS pg_trgm;",
            reverse_sql="-- pg_trgm extension is intentionally left installed on rollback.",
        ),
        # Step 2 — GIN trigram index on subject_name.
        # Accelerates: GenerationLog.objects.filter(subject_name__icontains="...")
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS gen_log_subject_trgm_idx
                ON knowledge_generation_log
                USING gin (subject_name gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS gen_log_subject_trgm_idx;",
        ),
        # Step 3 — GIN trigram index on topic_name.
        # Accelerates: GenerationLog.objects.filter(topic_name__icontains="...")
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS gen_log_topic_trgm_idx
                ON knowledge_generation_log
                USING gin (topic_name gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS gen_log_topic_trgm_idx;",
        ),
    ]
