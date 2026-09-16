"""
Migration 0006 — G3.9 `OverviewContent` (FEATURES_GROWTH_STACK.md §7.9a).

Additive only: one new table, `knowledge_overview_content`, holding the
LLM-written overview of a subject or module. No existing table, column, index
or constraint is touched — `generate_book_content` and `BookContent` are
unchanged by this migration (the G3.9 collision guarantee #2).

Generic (target_type, target_id) pointer, no FK: the seeded hierarchy stays
read-only to this feature, and the row survives a node rename or re-seed that
keeps its UUID.
"""

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("book_content", "0005_p36_trigram_indexes"),
    ]

    operations = [
        migrations.CreateModel(
            name="OverviewContent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "target_type",
                    models.CharField(
                        choices=[("subject", "Subject"), ("module", "Module")],
                        max_length=10,
                    ),
                ),
                (
                    "target_id",
                    models.UUIDField(
                        help_text="knowledge.Subject.id or knowledge.Module.id (no FK — see docstring)"
                    ),
                ),
                (
                    "content_markdown",
                    models.TextField(
                        help_text="The overview, grounded in the generated topic articles beneath the node."
                    ),
                ),
                (
                    "word_count",
                    models.IntegerField(default=0, help_text="Computed on save."),
                ),
                (
                    "quality_score",
                    models.FloatField(
                        default=0.0,
                        help_text="Heuristic 0–100 from the generator's gate.",
                    ),
                ),
                (
                    "generation_pass",
                    models.IntegerField(
                        default=1,
                        help_text="1 = first draft passed the gate; 2 = the retry did.",
                    ),
                ),
                (
                    "grounded_on",
                    models.IntegerField(
                        default=0,
                        help_text="How many generated topic articles fed the prompt.",
                    ),
                ),
                (
                    "is_published",
                    models.BooleanField(
                        default=False,
                        help_text="Served and rendered only when True.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "knowledge_overview_content",
                "ordering": ["target_type", "-created_at"],
                "indexes": [
                    models.Index(
                        fields=["target_type", "is_published"],
                        name="overview_target_pub_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("target_type", "target_id"),
                        name="overview_content_one_per_target",
                    )
                ],
            },
        ),
    ]
