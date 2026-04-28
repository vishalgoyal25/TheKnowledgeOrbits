"""
Migration 0007 — Phase D: add 'duplicate' to CaDailyProposal.status choices.

Django CharField choices are not enforced at the database level for PostgreSQL —
this migration records the change in migration history only; no ALTER TABLE runs.
The 'duplicate' status is set by generate_ca_proposals when an intra-day proposal
title overlaps >50% with an already-saved proposal in the same run.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("daily_ca", "0006_search_trigram_idx"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cadailyproposal",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending Review"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("generated", "Article Generated"),
                    ("failed", "Generation Failed"),
                    ("queued_next_run", "Queued for Next Run"),
                    ("duplicate", "Duplicate — skipped by title-overlap dedup"),
                ],
                db_index=True,
                default="pending",
                max_length=20,
            ),
        ),
    ]
