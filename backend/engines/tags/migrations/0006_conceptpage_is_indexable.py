"""
Migration 0006 — `ConceptPage.is_indexable`, stored (G3.3 / G3.11, 2026-09-16).

WHY
  The concept sitemap feed computed the G0.3 rule (ready AND >= 400 words AND
  >= 3 headings) by regex-scanning ~1,400 bodies on every cache miss. Fine on a
  laptop; on the free Render dyno, under the Vercel build's request storm, the
  scan exceeded the proxy timeout, Render answered 502, and `sitemap.ts` failed
  the deploy — correctly (FEATURES_GROWTH_STACK.md §15A.7). A stored, indexed
  boolean makes the feed a millisecond query.

WHAT
  1. AddField `is_indexable` (default False, indexed).
  2. RunPython backfill: one pass over ready rows, same rule as the model's
     save() (`engines.tags.text_rules.passes_index_rule`). Idempotent; reverse
     is a no-op (the column simply drops with the field).

Additive only. Bodies are never modified.
"""

from django.db import migrations, models

from engines.tags.text_rules import passes_index_rule


def backfill(apps, schema_editor):
    ConceptPage = apps.get_model("tags", "ConceptPage")
    alias = schema_editor.connection.alias
    ready = ConceptPage.objects.using(alias).filter(is_content_ready=True)
    indexable_ids = [
        c.pk
        for c in ready.only("pk", "body_md").iterator(chunk_size=200)
        if passes_index_rule(c.body_md)
    ]
    ConceptPage.objects.using(alias).filter(pk__in=indexable_ids).update(
        is_indexable=True
    )


class Migration(migrations.Migration):
    dependencies = [
        ("tags", "0005_p14_compound_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="conceptpage",
            name="is_indexable",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Ready AND body passes the G0.3 rule (>= 400 words, >= 3 headings). Computed on save.",
            ),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
