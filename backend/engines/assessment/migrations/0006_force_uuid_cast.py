from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("assessment", "0005_fix_user_uuid_fields"),
    ]

    operations = [
        # Explicitly cast columns to UUID because Django didn't apply the change
        migrations.RunSQL(
            sql="ALTER TABLE assessment_quiz_attempt ALTER COLUMN user_id TYPE uuid USING user_id::text::uuid;",
            reverse_sql="ALTER TABLE assessment_quiz_attempt ALTER COLUMN user_id TYPE integer USING user_id::text::integer;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE assessment_quiz ALTER COLUMN created_by_id TYPE uuid USING created_by_id::text::uuid;",
            reverse_sql="ALTER TABLE assessment_quiz ALTER COLUMN created_by_id TYPE integer USING created_by_id::text::integer;",
        ),
    ]
