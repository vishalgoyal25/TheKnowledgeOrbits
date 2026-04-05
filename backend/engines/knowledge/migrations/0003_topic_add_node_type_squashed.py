"""
engines/knowledge/migrations/0003_topic_add_node_type_squashed.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Squash replacement for 0003_topic_add_node_type.

WHY THIS FILE EXISTS:
  book_content/0001_initial.py depends on knowledge/0001 (not knowledge/0003),
  so Django may run book_content/0001 before knowledge/0003.
  book_content/0001 already adds node_type via IF NOT EXISTS.
  The original knowledge/0003 uses a plain AddField (no IF NOT EXISTS) and
  fails with "column already exists" on a fresh test database.

FIX:
  This file replaces 0003_topic_add_node_type with an idempotent RunSQL
  version. On existing databases where 0003 is already applied, Django marks
  this squash as applied automatically without re-running the SQL.
  On fresh databases (including test DBs), only this file runs — using
  IF NOT EXISTS so the column is added regardless of execution order.

RULES RESPECTED:
  - Does NOT modify the original 0003_topic_add_node_type.py (existing migration)
  - Is a NEW file (allowed per CLAUDE.md)
  - state_operations keeps Django's migration state accurate
  - Fully reversible via reverse_sql
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    # Replaces the original AddField migration with an idempotent RunSQL version.
    # Django will:
    #   - Fresh DB:   run only this migration (not the original 0003)
    #   - Existing DB where 0003 was already applied: mark this as applied, skip SQL
    replaces = [("knowledge", "0003_topic_add_node_type")]

    dependencies = [
        ("knowledge", "0002_topic_knowledge_t_module__67ee34_idx_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE knowledge_topic
                ADD COLUMN IF NOT EXISTS node_type VARCHAR(30) DEFAULT 'topic';

                CREATE INDEX IF NOT EXISTS knowledge_t_node_ty_770636_idx
                ON knowledge_topic(node_type);
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS knowledge_t_node_ty_770636_idx;
                ALTER TABLE knowledge_topic DROP COLUMN IF EXISTS node_type;
            """,
            state_operations=[
                migrations.AddField(
                    model_name="topic",
                    name="node_type",
                    field=models.CharField(
                        choices=[
                            ("subject_root", "Subject Root"),
                            ("module", "Module"),
                            ("topic", "Topic"),
                            ("subtopic", "Subtopic"),
                            ("sub_subtopic", "Sub-Subtopic"),
                        ],
                        default="topic",
                        help_text=(
                            "Hierarchy depth: subject_root → module → topic → "
                            "subtopic → sub_subtopic. Drives graph node visual "
                            "type and hamburger navbar depth."
                        ),
                        max_length=30,
                    ),
                ),
                migrations.AddIndex(
                    model_name="topic",
                    index=models.Index(
                        fields=["node_type"],
                        name="knowledge_t_node_ty_770636_idx",
                    ),
                ),
            ],
        ),
    ]
