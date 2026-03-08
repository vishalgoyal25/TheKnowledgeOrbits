from django.db import migrations


class Migration(migrations.Migration):
    """
    Manual migration to cast User-related foreign keys from Integer to UUID.
    This fixes a schema mismatch that occurred during the transition to a custom UUID-based User model.
    """

    dependencies = [
        ("article_generation", "0003_remove_article_article_created_by_idx_and_more"),
    ]

    operations = [
        # Explicitly cast columns to UUID to match the custom User model
        migrations.RunSQL(
            sql="ALTER TABLE article_article ALTER COLUMN created_by_id TYPE uuid USING created_by_id::text::uuid;",
            reverse_sql="ALTER TABLE article_article ALTER COLUMN created_by_id TYPE integer USING created_by_id::text::integer;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE article_article ALTER COLUMN published_by_id TYPE uuid USING published_by_id::text::uuid;",
            reverse_sql="ALTER TABLE article_article ALTER COLUMN published_by_id TYPE integer USING published_by_id::text::integer;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE article_generation_job ALTER COLUMN requested_by_id TYPE uuid USING requested_by_id::text::uuid;",
            reverse_sql="ALTER TABLE article_generation_job ALTER COLUMN requested_by_id TYPE integer USING requested_by_id::text::integer;",
        ),
    ]
