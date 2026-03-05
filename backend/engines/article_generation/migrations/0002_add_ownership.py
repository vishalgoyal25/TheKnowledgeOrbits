"""
Add ownership fields to Article model (PKB Extension).
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("article_generation", "0001_initial"),
    ]

    operations = [
        # Add created_by field
        migrations.AddField(
            model_name="article",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                help_text="User who created this article (NULL = system/admin)",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="created_articles",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # Add is_public field
        migrations.AddField(
            model_name="article",
            name="is_public",
            field=models.BooleanField(
                default=True, help_text="Is this article publicly visible?"
            ),
        ),
        # Add indexes
        migrations.AddIndex(
            model_name="article",
            index=models.Index(fields=["created_by"], name="article_created_by_idx"),
        ),
        migrations.AddIndex(
            model_name="article",
            index=models.Index(fields=["is_public"], name="article_is_public_idx"),
        ),
        migrations.AddIndex(
            model_name="article",
            index=models.Index(
                fields=["created_by", "is_public"], name="article_owner_public_idx"
            ),
        ),
    ]
