"""
G3.10 — backfill `slug` on every existing Subject, Module and Topic.

Deterministic on purpose: rows are walked in (order_index, name, id) order per
model, so local and Supabase mint identical slugs and a URL built against one
resolves on the other. Uses the same `unique_slug` as the models' save(), so
a row created tomorrow cannot collide with one backfilled today.

Idempotent: rows that already carry a slug are skipped, so re-running (or
running on a DB where some rows were minted by save() before this migration
applied) changes nothing.

Reverse is a no-op — clearing slugs would break every URL already shared.
"""

from django.db import migrations

from engines.knowledge.services.slug_service import unique_slug

SLUG_MAX_LENGTH = 230
MODELS = ("Subject", "Module", "Topic")


def backfill(apps, schema_editor):
    db = schema_editor.connection.alias
    for model_name in MODELS:
        model = apps.get_model("knowledge", model_name)
        rows = (
            model.objects.using(db)
            .filter(slug__isnull=True)
            .order_by("order_index", "name", "id")
        )
        for row in rows.iterator(chunk_size=200):
            row.slug = unique_slug(
                model,
                row.name,
                max_length=SLUG_MAX_LENGTH,
                using=db,
                exclude_pk=row.pk,
            )
            # update_fields: touch only the slug — never `updated_at` or anything
            # the content pipeline reads. `save()` on a historical model does not
            # run the mixin anyway; this is a plain column write.
            row.save(using=db, update_fields=["slug"])


def noop(apps, schema_editor):
    """Slugs are promises once shared; reversing the schema (0006) is enough."""


class Migration(migrations.Migration):
    dependencies = [
        ("knowledge", "0006_slugs"),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
