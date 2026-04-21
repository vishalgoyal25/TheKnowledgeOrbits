"""
Migration 0006 — Django state sync for CAChunk.search_vector

WHY THIS EXISTS:
  Migration 0005 added the search_vector column via RunSQL (ALTER TABLE ADD COLUMN).
  Django's migration state doesn't track raw SQL — it only tracks AddField/etc.
  So Django detected a model change not reflected in state and auto-generated this.

WHY SeparateDatabaseAndState:
  The column ALREADY EXISTS on the database (added by 0005's RunSQL).
  Running a plain AddField here would fail: "column search_vector already exists".
  SeparateDatabaseAndState lets us update Django's internal migration state (AddField)
  WITHOUT executing any SQL against the real database (database_operations=[]).

Result: Django now knows about the field. No duplicate column error.
"""

import django.contrib.postgres.search
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("current_affairs", "0005_cachunk_search_vector"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            # Tell Django's migration state: "this field now exists"
            state_operations=[
                migrations.AddField(
                    model_name="cachunk",
                    name="search_vector",
                    field=django.contrib.postgres.search.SearchVectorField(
                        blank=True,
                        help_text="Precomputed tsvector for BM25 full-text search (auto-populated on save).",
                        null=True,
                    ),
                ),
            ],
            # Skip the SQL — column already added by 0005's RunSQL
            database_operations=[],
        ),
    ]
