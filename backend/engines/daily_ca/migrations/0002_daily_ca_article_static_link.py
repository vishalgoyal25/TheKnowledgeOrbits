"""
Phase J Migration — DailyCaArticle + DailyCaStaticLink tables.

Also converts CaDailyProposal.generated_article_id from plain UUIDField
to a proper ForeignKey pointing at DailyCaArticle (deferred from Phase F1).
"""

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("daily_ca", "0001_initial"),
        ("book_content", "0003_alter_bookchunk_search_vector_and_more"),
        ("knowledge", "0004_topic_add_content_status_squashed"),
    ]

    operations = [
        # ── J1: DailyCaArticle ────────────────────────────────────────────────
        migrations.CreateModel(
            name="DailyCaArticle",
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
                ("title", models.CharField(max_length=500)),
                (
                    "slug",
                    models.SlugField(
                        help_text="URL slug: {date}-{title-slug}, e.g. 2026-04-10-india-fast-breeder-reactor",
                        max_length=550,
                        unique=True,
                    ),
                ),
                (
                    "subject_name",
                    models.CharField(
                        blank=True,
                        help_text="UPSC subject name (denormalised from topic.subject.name)",
                        max_length=200,
                    ),
                ),
                (
                    "gs_paper",
                    models.CharField(
                        blank=True,
                        help_text="GS paper classification: GS1 / GS2 / GS3 / GS4",
                        max_length=10,
                    ),
                ),
                (
                    "published_date",
                    models.DateField(
                        db_index=True,
                        help_text="The calendar date this article is published for",
                    ),
                ),
                (
                    "body_md",
                    models.TextField(
                        help_text="Raw LLM output markdown — preserves [[concept]] brackets for audit",
                    ),
                ),
                (
                    "body_md_processed",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Processed markdown — [[term]] replaced with [term](/concepts/slug) links",
                    ),
                ),
                (
                    "news_context",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="3-sentence summary of the news that triggered this article",
                    ),
                ),
                (
                    "sources_used",
                    models.JSONField(
                        default=list,
                        help_text="List of [{source_name, url, title}] dicts",
                    ),
                ),
                (
                    "hero_image_url",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=1000,
                        help_text="Cloudinary URL for hero image",
                    ),
                ),
                (
                    "ca_chunk_ids",
                    models.JSONField(
                        default=list,
                        help_text="UUIDs of the top-3 CAChunks used as source",
                    ),
                ),
                (
                    "quality_score",
                    models.FloatField(
                        default=0.0,
                        help_text="0.0–10.0 quality signal computed post-generation",
                    ),
                ),
                (
                    "is_published",
                    models.BooleanField(
                        db_index=True,
                        default=False,
                        help_text="False = awaiting admin review. True = live on /daily-ca/",
                    ),
                ),
                (
                    "generation_metadata",
                    models.JSONField(
                        default=dict,
                        help_text="Audit dict: groq_model, word_count, had_static_anchor, etc.",
                    ),
                ),
                (
                    "order_on_date",
                    models.PositiveSmallIntegerField(
                        default=0,
                        help_text="Display order within a date (1–10)",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "topic",
                    models.ForeignKey(
                        blank=True,
                        help_text="UPSC syllabus topic this article maps to",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="daily_ca_articles",
                        to="knowledge.topic",
                    ),
                ),
                (
                    "static_background",
                    models.ForeignKey(
                        blank=True,
                        help_text="BookContent used as factual anchor during generation",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ca_articles",
                        to="book_content.bookcontent",
                    ),
                ),
            ],
            options={
                "db_table": "daily_ca_article",
                "ordering": ["published_date", "order_on_date"],
                "indexes": [
                    models.Index(
                        fields=["-published_date"],
                        name="daily_ca_art_pub_date_desc_idx",
                    ),
                    models.Index(
                        fields=["published_date", "is_published"],
                        name="daily_ca_art_pub_ispub_idx",
                    ),
                    models.Index(
                        fields=["slug"],
                        name="daily_ca_art_slug_idx",
                    ),
                    models.Index(
                        fields=["topic"],
                        name="daily_ca_art_topic_idx",
                    ),
                ],
            },
        ),
        # ── J2: DailyCaStaticLink ─────────────────────────────────────────────
        migrations.CreateModel(
            name="DailyCaStaticLink",
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
                    "link_reason",
                    models.CharField(
                        choices=[
                            ("same_topic", "Same Topic"),
                            ("background", "Background Context"),
                            ("related_concept", "Related Concept"),
                        ],
                        default="same_topic",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "daily_article",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="static_links",
                        to="daily_ca.dailycaarticle",
                    ),
                ),
                (
                    "book_content",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ca_links",
                        to="book_content.bookcontent",
                    ),
                ),
            ],
            options={
                "db_table": "daily_ca_static_link",
                "indexes": [
                    models.Index(
                        fields=["daily_article"],
                        name="daily_ca_sl_article_idx",
                    ),
                    models.Index(
                        fields=["book_content"],
                        name="daily_ca_sl_bookcontent_idx",
                    ),
                ],
                "unique_together": {("daily_article", "book_content")},
            },
        ),
        # ── CaDailyProposal.generated_article_id → proper FK ─────────────────
        # Convert from plain UUIDField (Phase F1) to ForeignKey now that
        # DailyCaArticle exists. SET_NULL so deleting an article doesn't
        # erase the proposal audit record.
        migrations.AlterField(
            model_name="cadailyproposal",
            name="generated_article_id",
            field=models.ForeignKey(
                blank=True,
                db_column="generated_article_id",
                help_text="DailyCaArticle generated from this proposal",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="proposal",
                to="daily_ca.dailycaarticle",
            ),
        ),
    ]
