"""
Migration 0001 — Phase B: initial Social Interaction Engine schema.

Creates four tables:
  social_like     — one like per (user, content_type, content_id)
  social_comment  — threaded comments, 1 level deep; soft-delete + flag support
  social_share    — share audit log per platform
  social_count    — denormalised counter cache; never modified manually
"""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── social_like ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Like",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "content_type",
                    models.CharField(
                        choices=[
                            ("daily_ca_article", "Daily CA Article"),
                            ("book_article", "Book / Static Article"),
                            ("quiz", "Quiz"),
                        ],
                        db_index=True,
                        max_length=50,
                    ),
                ),
                ("content_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="likes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "social_like",
            },
        ),
        migrations.AddIndex(
            model_name="like",
            index=models.Index(
                fields=["content_type", "content_id"],
                name="social_like_ct_cid_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="like",
            index=models.Index(
                fields=["user", "content_type"],
                name="social_like_user_ct_idx",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="like",
            unique_together={("user", "content_type", "content_id")},
        ),
        # ── social_comment ────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Comment",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "content_type",
                    models.CharField(
                        choices=[
                            ("daily_ca_article", "Daily CA Article"),
                            ("book_article", "Book / Static Article"),
                            ("quiz", "Quiz"),
                        ],
                        db_index=True,
                        max_length=50,
                    ),
                ),
                ("content_id", models.UUIDField(db_index=True)),
                ("body", models.TextField(max_length=1000)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="replies",
                        to="social.comment",
                    ),
                ),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("is_flagged", models.BooleanField(db_index=True, default=False)),
                ("edited_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "social_comment",
                "ordering": ["created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="comment",
            index=models.Index(
                fields=["content_type", "content_id", "created_at"],
                name="social_comment_ct_cid_ts_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="comment",
            index=models.Index(
                fields=["parent"],
                name="social_comment_parent_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="comment",
            index=models.Index(
                fields=["user"],
                name="social_comment_user_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="comment",
            index=models.Index(
                fields=["is_deleted", "is_flagged"],
                name="social_comment_mod_idx",
            ),
        ),
        # ── social_share ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Share",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "content_type",
                    models.CharField(
                        choices=[
                            ("daily_ca_article", "Daily CA Article"),
                            ("book_article", "Book / Static Article"),
                            ("quiz", "Quiz"),
                        ],
                        db_index=True,
                        max_length=50,
                    ),
                ),
                ("content_id", models.UUIDField(db_index=True)),
                (
                    "platform",
                    models.CharField(
                        choices=[
                            ("copy_link", "Copy Link"),
                            ("whatsapp", "WhatsApp"),
                            ("twitter", "Twitter / X"),
                            ("telegram", "Telegram"),
                            ("other", "Other"),
                        ],
                        default="copy_link",
                        max_length=20,
                    ),
                ),
                ("shared_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="shares",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "social_share",
            },
        ),
        migrations.AddIndex(
            model_name="share",
            index=models.Index(
                fields=["content_type", "content_id"],
                name="social_share_ct_cid_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="share",
            index=models.Index(
                fields=["user"],
                name="social_share_user_idx",
            ),
        ),
        # ── social_count ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name="SocialCount",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "content_type",
                    models.CharField(
                        choices=[
                            ("daily_ca_article", "Daily CA Article"),
                            ("book_article", "Book / Static Article"),
                            ("quiz", "Quiz"),
                        ],
                        max_length=50,
                    ),
                ),
                ("content_id", models.UUIDField()),
                ("like_count", models.PositiveIntegerField(default=0)),
                ("comment_count", models.PositiveIntegerField(default=0)),
                ("share_count", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "social_count",
            },
        ),
        migrations.AddIndex(
            model_name="socialcount",
            index=models.Index(
                fields=["content_type", "content_id"],
                name="social_count_ct_cid_idx",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="socialcount",
            unique_together={("content_type", "content_id")},
        ),
    ]
