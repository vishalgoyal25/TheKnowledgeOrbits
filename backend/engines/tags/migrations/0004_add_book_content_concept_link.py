# Hand-written migration — replaces auto-generated version.
#
# Problem the auto-generated migration had:
#   The DB column "daily_ca_article_id" already exists (plain UUID from 0003).
#   Auto-generator emitted AddField(daily_ca_article) which tried to ADD COLUMN
#   daily_ca_article_id again → ProgrammingError: column already exists.
#
# Fix:
#   Use SeparateDatabaseAndState for the daily_ca_article field conversion:
#   - DB operation  → RunSQL: just adds FK constraint on the existing column.
#   - State operation → RemoveField(daily_ca_article_id) + AddField(daily_ca_article FK).
#   book_content_article is a brand-new column → normal AddField (safe).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("book_content", "0003_alter_bookchunk_search_vector_and_more"),
        ("daily_ca", "0004_add_news_category"),
        ("tags", "0003_alter_conceptarticlelink_daily_ca_article_id"),
    ]

    operations = [
        # 1. Drop the old index on daily_ca_article_id
        migrations.RemoveIndex(
            model_name="conceptarticlelink",
            name="concept_art_daily_c_71e14b_idx",
        ),
        # 2. Drop old unique_together
        migrations.AlterUniqueTogether(
            name="conceptarticlelink",
            unique_together=set(),
        ),
        # 3. Add brand-new book_content_article column (safe — does not exist yet)
        migrations.AddField(
            model_name="conceptarticlelink",
            name="book_content_article",
            field=models.ForeignKey(
                blank=True,
                help_text="BookContent article this concept is linked from (null if daily_ca link)",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="concept_links",
                to="book_content.bookcontent",
            ),
        ),
        # 4. Convert daily_ca_article_id UUIDField → FK without touching the column.
        #    The column already exists — we only add the FK constraint at DB level.
        #    At state level we swap out the UUIDField for the proper FK field.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE concept_article_link
                        ADD CONSTRAINT concept_art_daily_ca_fk
                        FOREIGN KEY (daily_ca_article_id)
                        REFERENCES daily_ca_article(id)
                        ON DELETE CASCADE
                        DEFERRABLE INITIALLY DEFERRED;
                    """,
                    reverse_sql="""
                        ALTER TABLE concept_article_link
                        DROP CONSTRAINT concept_art_daily_ca_fk;
                    """,
                ),
            ],
            state_operations=[
                # Remove old plain UUIDField from Django state
                migrations.RemoveField(
                    model_name="conceptarticlelink",
                    name="daily_ca_article_id",
                ),
                # Register the FK field in Django state (maps to same DB column)
                migrations.AddField(
                    model_name="conceptarticlelink",
                    name="daily_ca_article",
                    field=models.ForeignKey(
                        blank=True,
                        help_text="DailyCaArticle this concept is linked from (null if book_content link)",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="concept_links",
                        to="daily_ca.dailycaarticle",
                    ),
                ),
            ],
        ),
        # 5. Add index on daily_ca_article (same DB column as before)
        migrations.AddIndex(
            model_name="conceptarticlelink",
            index=models.Index(
                fields=["daily_ca_article"],
                name="concept_art_daily_c_71e14b_idx",
            ),
        ),
        # 6. Add index on book_content_article (new column)
        migrations.AddIndex(
            model_name="conceptarticlelink",
            index=models.Index(
                fields=["book_content_article"],
                name="concept_art_book_co_5fbd30_idx",
            ),
        ),
        # 7. Unique constraint: one concept per daily_ca_article
        migrations.AddConstraint(
            model_name="conceptarticlelink",
            constraint=models.UniqueConstraint(
                condition=models.Q(daily_ca_article__isnull=False),
                fields=("concept_page", "daily_ca_article"),
                name="unique_concept_ca_article",
            ),
        ),
        # 8. Unique constraint: one concept per book_content_article
        migrations.AddConstraint(
            model_name="conceptarticlelink",
            constraint=models.UniqueConstraint(
                condition=models.Q(book_content_article__isnull=False),
                fields=("concept_page", "book_content_article"),
                name="unique_concept_book_article",
            ),
        ),
    ]
