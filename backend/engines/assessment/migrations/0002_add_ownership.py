"""
Add ownership fields to Quiz model (PKB Extension).
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('assessment', '0001_initial'),
    ]

    operations = [
        # Add created_by field
        migrations.AddField(
            model_name='quiz',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                help_text='User who created this quiz (NULL = system/admin)',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='created_quizzes',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        
        # Add is_public field
        migrations.AddField(
            model_name='quiz',
            name='is_public',
            field=models.BooleanField(
                default=True,
                help_text='Is quiz publicly accessible?'
            ),
        ),
        
        # Add indexes
        migrations.AddIndex(
            model_name='quiz',
            index=models.Index(fields=['created_by'], name='quiz_created_by_idx'),
        ),
        migrations.AddIndex(
            model_name='quiz',
            index=models.Index(fields=['is_public'], name='quiz_is_public_idx'),
        ),
        migrations.AddIndex(
            model_name='quiz',
            index=models.Index(fields=['created_by', 'is_public'], name='quiz_owner_public_idx'),
        ),
    ]
    