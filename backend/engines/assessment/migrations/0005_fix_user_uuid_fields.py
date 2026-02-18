# Generated manually to fix UUID mismatch

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('assessment', '0004_remove_quiz_quiz_created_by_idx_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # SAFEGUARD: Clear existing integer references to avoid casting errors
        migrations.RunSQL(
            "DELETE FROM assessment_quiz_attempt WHERE user_id IS NOT NULL;",
            reverse_sql=migrations.RunSQL.noop
        ),
        migrations.RunSQL(
            "UPDATE assessment_quiz SET created_by_id = NULL WHERE created_by_id IS NOT NULL;",
            reverse_sql=migrations.RunSQL.noop
        ),
        
        # Alter user field to ensure UUID reference
        migrations.AlterField(
            model_name='quizattempt',
            name='user',
            field=models.ForeignKey(
                blank=True,
                help_text='User taking quiz (null for guest mode)',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='quiz_attempts',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        
        # Alter created_by field to ensure UUID reference
        migrations.AlterField(
            model_name='quiz',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                help_text='User who created this quiz (NULL = system/admin)',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='created_quizzes',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
