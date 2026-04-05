"""
Squash replacement for 0004_topic_add_content_status.
Same root cause as 0003: book_content/0001_initial adds content_status via
IF NOT EXISTS before this migration runs, causing plain AddField to fail.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    replaces = [("knowledge", "0004_topic_add_content_status")]

    dependencies = [
        ("knowledge", "0003_topic_add_node_type"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE knowledge_topic
                ADD COLUMN IF NOT EXISTS content_status VARCHAR(20) DEFAULT 'empty';

                CREATE INDEX IF NOT EXISTS knowledge_t_content_9d9c3f_idx
                ON knowledge_topic(content_status);
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS knowledge_t_content_9d9c3f_idx;
                ALTER TABLE knowledge_topic DROP COLUMN IF EXISTS content_status;
            """,
            state_operations=[
                migrations.AddField(
                    model_name="topic",
                    name="content_status",
                    field=models.CharField(
                        default="empty",
                        help_text="Generation status of this node's book content. Values: empty | generating | book_quality | failed",
                        max_length=20,
                    ),
                ),
                migrations.AddIndex(
                    model_name="topic",
                    index=models.Index(
                        fields=["content_status"],
                        name="knowledge_t_content_9d9c3f_idx",
                    ),
                ),
            ],
        ),
    ]
