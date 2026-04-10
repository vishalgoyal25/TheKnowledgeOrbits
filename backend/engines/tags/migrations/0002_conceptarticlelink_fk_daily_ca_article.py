"""
Phase J Migration (tags engine) — Add FK constraint on ConceptArticleLink.

In Phase C, ConceptArticleLink.daily_ca_article_id was stored as a plain UUIDField
because DailyCaArticle didn't exist yet.

Now that DailyCaArticle exists (Phase J), we convert it to a proper ForeignKey
with CASCADE delete — so deleting an article also cleans up its concept links.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tags", "0001_initial"),
        ("daily_ca", "0002_daily_ca_article_static_link"),
    ]

    operations = [
        migrations.AlterField(
            model_name="conceptarticlelink",
            name="daily_ca_article_id",
            field=models.ForeignKey(
                db_column="daily_ca_article_id",
                help_text="The DailyCaArticle this concept is linked from",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="concept_links",
                to="daily_ca.dailycaarticle",
            ),
        ),
    ]
