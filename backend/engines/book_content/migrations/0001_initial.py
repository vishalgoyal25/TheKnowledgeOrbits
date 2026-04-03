"""
Book Content Engine — Initial Migration
Creates all 6 new tables for the book content generation system.
Adds 3 additive columns to existing knowledge_topic table.
Zero destructive changes — additive only.
"""

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("knowledge", "0001_initial"),
    ]

    operations = [
        # ── Table 1: knowledge_book_plan ──────────────────────────────────────
        migrations.CreateModel(
            name="BookPlan",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        help_text="Unique identifier for this book plan.",
                    ),
                ),
                (
                    "toc_json",
                    models.JSONField(
                        default=list,
                        help_text=(
                            "AI-generated complete Table of Contents. "
                            "Structure: [{module, order, topics: [{name, subtopics, prerequisites}]}]"
                        ),
                    ),
                ),
                (
                    "concept_registry",
                    models.JSONField(
                        default=dict,
                        help_text=(
                            "Maps concept_name_lower → {topic_id (uuid), topic_label}. "
                            "Updated after each article is generated. Powers Layer 3 cross-references."
                        ),
                    ),
                ),
                (
                    "prerequisite_chains",
                    models.JSONField(
                        default=dict,
                        help_text=(
                            "Maps topic_name → [prerequisite topic names]. "
                            "Defines reading order for students."
                        ),
                    ),
                ),
                (
                    "reading_order",
                    models.JSONField(
                        default=list,
                        help_text="Flat ordered list of topics for linear book-reading mode.",
                    ),
                ),
                (
                    "generation_status",
                    models.CharField(
                        default="planned",
                        max_length=20,
                        help_text=(
                            "Status of content generation for this subject. "
                            "Values: planned | generating | partial | complete"
                        ),
                    ),
                ),
                (
                    "topics_planned",
                    models.IntegerField(
                        default=0,
                        help_text="Total number of topic nodes planned in this subject's TOC.",
                    ),
                ),
                (
                    "topics_completed",
                    models.IntegerField(
                        default=0,
                        help_text="Number of topic nodes with generated book content.",
                    ),
                ),
                (
                    "avg_quality_score",
                    models.FloatField(
                        default=0.0,
                        help_text="Rolling average quality score across all generated articles in this subject.",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="When this book plan was first created.",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True,
                        help_text="Last time this book plan was updated.",
                    ),
                ),
                (
                    "subject",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="book_plan",
                        to="knowledge.subject",
                        help_text="The subject this book plan belongs to.",
                    ),
                ),
            ],
            options={
                "db_table": "knowledge_book_plan",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="BookPlan",
            index=models.Index(
                fields=["generation_status"],
                name="book_plan_status_idx",
            ),
        ),
        # ── Table 2: knowledge_book_content ───────────────────────────────────
        migrations.CreateModel(
            name="BookContent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        help_text="Unique identifier for this book content entry.",
                    ),
                ),
                (
                    "content_markdown",
                    models.TextField(
                        help_text=(
                            "Full generated Markdown article. "
                            "Produced by Layer 2 Quality Engine (section-by-section generation)."
                        ),
                    ),
                ),
                (
                    "formatted_content",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text=(
                            "Phase 4.5B output: content WITH tables + callouts injected. "
                            "Frontend renders this if available, falls back to content_markdown."
                        ),
                    ),
                ),
                (
                    "word_count",
                    models.IntegerField(
                        default=0,
                        help_text="Word count of content_markdown. Computed on save.",
                    ),
                ),
                (
                    "quality_score",
                    models.FloatField(
                        default=0.0,
                        help_text=(
                            "Self-critique quality score (0-100) from Layer 2. "
                            "Articles below 65 are auto-refined before saving."
                        ),
                    ),
                ),
                (
                    "critique_log",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Full JSON output of the self-critique pass. Audit trail.",
                    ),
                ),
                (
                    "generation_pass",
                    models.IntegerField(
                        default=1,
                        help_text="How many refinement passes the article took. 1=first pass passed.",
                    ),
                ),
                (
                    "source_mode",
                    models.CharField(
                        default="wiki_only",
                        max_length=30,
                        help_text="Which sources were used. Values: wiki_only | ncert_wiki",
                    ),
                ),
                (
                    "has_tables",
                    models.BooleanField(
                        default=False,
                        help_text="Whether this article contains generated comparison/summary tables.",
                    ),
                ),
                (
                    "has_media",
                    models.BooleanField(
                        default=False,
                        help_text="Whether this article has image/infographic placeholders.",
                    ),
                ),
                (
                    "is_published",
                    models.BooleanField(
                        default=False,
                        help_text="Whether this content is visible to students.",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="When this article was first generated.",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True,
                        help_text="Last time this article was updated or refined.",
                    ),
                ),
                (
                    "topic",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="book_content",
                        to="knowledge.topic",
                        help_text="The knowledge topic node this content belongs to.",
                    ),
                ),
                (
                    "subject",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="book_contents",
                        to="knowledge.subject",
                        help_text="Denormalized subject FK for fast filtering without JOIN chain.",
                    ),
                ),
            ],
            options={
                "db_table": "knowledge_book_content",
                "ordering": ["-quality_score", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="BookContent",
            index=models.Index(
                fields=["subject", "is_published"],
                name="book_content_subject_pub_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="BookContent",
            index=models.Index(
                fields=["quality_score"],
                name="book_content_quality_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="BookContent",
            index=models.Index(
                fields=["topic"],
                name="book_content_topic_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="BookContent",
            index=models.Index(
                fields=["source_mode"],
                name="book_content_source_idx",
            ),
        ),
        # ── Table 3: knowledge_topic_relation ─────────────────────────────────
        migrations.CreateModel(
            name="TopicRelation",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        help_text="Unique identifier for this topic relation.",
                    ),
                ),
                (
                    "relation_type",
                    models.CharField(
                        default="related_to",
                        max_length=30,
                        help_text=(
                            "Type of relationship. "
                            "Values: related_to | prerequisite | cross_subject | contrast | applies_to"
                        ),
                    ),
                ),
                (
                    "similarity_score",
                    models.FloatField(
                        default=0.0,
                        help_text=(
                            "pgvector cosine similarity score (0.0-1.0). "
                            "Populated by cross-linker after embeddings exist."
                        ),
                    ),
                ),
                (
                    "is_auto_detected",
                    models.BooleanField(
                        default=True,
                        help_text="True=auto-detected by similarity engine. False=manually added.",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="When this relation was created.",
                    ),
                ),
                (
                    "source_topic",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="outgoing_relations",
                        to="knowledge.topic",
                        help_text="The source topic in this directional relationship.",
                    ),
                ),
                (
                    "target_topic",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="incoming_relations",
                        to="knowledge.topic",
                        help_text="The target topic this relation points to.",
                    ),
                ),
            ],
            options={
                "db_table": "knowledge_topic_relation",
                "ordering": ["-similarity_score"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="TopicRelation",
            unique_together={("source_topic", "target_topic")},
        ),
        migrations.AddIndex(
            model_name="TopicRelation",
            index=models.Index(
                fields=["source_topic", "relation_type"],
                name="topic_rel_source_type_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="TopicRelation",
            index=models.Index(
                fields=["target_topic"],
                name="topic_rel_target_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="TopicRelation",
            index=models.Index(
                fields=["relation_type"],
                name="topic_rel_type_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="TopicRelation",
            index=models.Index(
                fields=["relation_type"],
                name="topic_rel_cross_subject_idx",
                condition=models.Q(relation_type="cross_subject"),
            ),
        ),
        # ── Table 4: knowledge_cross_reference ────────────────────────────────
        migrations.CreateModel(
            name="CrossReference",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        help_text="Unique identifier for this cross-reference.",
                    ),
                ),
                (
                    "ref_type",
                    models.CharField(
                        default="see_also",
                        max_length=30,
                        help_text=(
                            "Type of reference. "
                            "Values: see_also | prerequisite | continuation | contrast"
                        ),
                    ),
                ),
                (
                    "ref_text",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=300,
                        help_text="The concept phrase in the source article that triggered this reference.",
                    ),
                ),
                (
                    "display_label",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=300,
                        help_text=(
                            "Human-readable link text shown to student. "
                            "Example: 'Anti-Defection Law → Tenth Schedule'"
                        ),
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="When this cross-reference was injected.",
                    ),
                ),
                (
                    "source_content",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="outgoing_references",
                        to="book_content.bookcontent",
                        help_text="The article that contains the reference.",
                    ),
                ),
                (
                    "target_content",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="incoming_references",
                        to="book_content.bookcontent",
                        help_text="The article being referenced.",
                    ),
                ),
            ],
            options={
                "db_table": "knowledge_cross_reference",
                "ordering": ["ref_type"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="CrossReference",
            unique_together={("source_content", "target_content")},
        ),
        migrations.AddIndex(
            model_name="CrossReference",
            index=models.Index(
                fields=["source_content"],
                name="crossref_source_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="CrossReference",
            index=models.Index(
                fields=["target_content"],
                name="crossref_target_idx",
            ),
        ),
        # ── Table 5: knowledge_content_media ──────────────────────────────────
        migrations.CreateModel(
            name="ContentMedia",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        help_text="Unique identifier for this media asset.",
                    ),
                ),
                (
                    "media_type",
                    models.CharField(
                        max_length=30,
                        help_text=(
                            "Type of media. "
                            "Values: image | diagram | table_image | infographic | video | placeholder"
                        ),
                    ),
                ),
                (
                    "cloudinary_url",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Cloudinary CDN URL. Empty if placeholder not yet fulfilled.",
                    ),
                ),
                (
                    "youtube_url",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="YouTube embed URL for video content.",
                    ),
                ),
                (
                    "position",
                    models.CharField(
                        default="inline",
                        max_length=20,
                        help_text="Where in the article this media appears. Values: hero | inline | end",
                    ),
                ),
                (
                    "position_marker",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text=(
                            "The exact marker string in content_markdown where this media is inserted. "
                            "Example: '>[!infographic: Map of British India 1773]<' "
                            "Frontend replaces this marker with the rendered component."
                        ),
                    ),
                ),
                (
                    "caption",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Caption text displayed below the media.",
                    ),
                ),
                (
                    "alt_text",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=500,
                        help_text="Accessibility alt text for images.",
                    ),
                ),
                (
                    "display_order",
                    models.IntegerField(
                        default=0,
                        help_text="Order of this media within the article.",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="When this media asset was created.",
                    ),
                ),
                (
                    "content",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="media_assets",
                        to="book_content.bookcontent",
                        help_text="The book content article this media belongs to.",
                    ),
                ),
            ],
            options={
                "db_table": "knowledge_content_media",
                "ordering": ["display_order"],
            },
        ),
        migrations.AddIndex(
            model_name="ContentMedia",
            index=models.Index(
                fields=["content", "display_order"],
                name="content_media_order_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="ContentMedia",
            index=models.Index(
                fields=["media_type"],
                name="content_media_type_idx",
            ),
        ),
        # ── Table 6: knowledge_generation_log ────────────────────────────────
        migrations.CreateModel(
            name="GenerationLog",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        help_text="Unique identifier for this generation log entry.",
                    ),
                ),
                (
                    "topic_name",
                    models.CharField(
                        max_length=500,
                        help_text="Name of the topic being generated.",
                    ),
                ),
                (
                    "subject_name",
                    models.CharField(
                        max_length=300,
                        help_text="Name of the subject this topic belongs to.",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        max_length=20,
                        help_text="Outcome of this generation run. Values: success | failed | skipped",
                    ),
                ),
                (
                    "nodes_created",
                    models.IntegerField(
                        default=0,
                        help_text="Number of new BookContent records created in this run.",
                    ),
                ),
                (
                    "relations_created",
                    models.IntegerField(
                        default=0,
                        help_text="Number of new TopicRelation records created in this run.",
                    ),
                ),
                (
                    "cross_refs_created",
                    models.IntegerField(
                        default=0,
                        help_text="Number of CrossReference records injected in this run.",
                    ),
                ),
                (
                    "quality_score",
                    models.FloatField(
                        default=0.0,
                        help_text="Quality score of the generated article (0-100).",
                    ),
                ),
                (
                    "word_count",
                    models.IntegerField(
                        default=0,
                        help_text="Word count of the generated article.",
                    ),
                ),
                (
                    "error_message",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Full error message if status=failed.",
                    ),
                ),
                (
                    "generation_time_seconds",
                    models.IntegerField(
                        default=0,
                        help_text="Total wall-clock seconds taken for this generation run.",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="When this log entry was created (= when generation ran).",
                    ),
                ),
            ],
            options={
                "db_table": "knowledge_generation_log",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="GenerationLog",
            index=models.Index(
                fields=["status", "-created_at"],
                name="gen_log_status_time_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="GenerationLog",
            index=models.Index(
                fields=["subject_name"],
                name="gen_log_subject_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="GenerationLog",
            index=models.Index(
                fields=["topic_name"],
                name="gen_log_topic_idx",
            ),
        ),
        # ── Additive columns on existing knowledge_topic table ────────────────
        # Uses RunSQL — additive only, no existing columns touched.
        migrations.RunSQL(
            sql="""
                ALTER TABLE knowledge_topic ADD COLUMN IF NOT EXISTS node_type VARCHAR(30) DEFAULT 'topic';
                ALTER TABLE knowledge_topic ADD COLUMN IF NOT EXISTS graph_position JSONB DEFAULT '{}';
                ALTER TABLE knowledge_topic ADD COLUMN IF NOT EXISTS content_status VARCHAR(20) DEFAULT 'empty';

                CREATE INDEX IF NOT EXISTS topic_node_type_idx ON knowledge_topic(node_type);
                CREATE INDEX IF NOT EXISTS topic_content_status_idx ON knowledge_topic(content_status);
                CREATE INDEX IF NOT EXISTS topic_parent_idx ON knowledge_topic(parent_topic_id) WHERE parent_topic_id IS NOT NULL;
                CREATE INDEX IF NOT EXISTS topic_subject_idx ON knowledge_topic(subject_id, is_active);
                CREATE INDEX IF NOT EXISTS topic_module_idx ON knowledge_topic(module_id, order_index);
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS topic_node_type_idx;
                DROP INDEX IF EXISTS topic_content_status_idx;
                DROP INDEX IF EXISTS topic_parent_idx;
                DROP INDEX IF EXISTS topic_subject_idx;
                DROP INDEX IF EXISTS topic_module_idx;
                ALTER TABLE knowledge_topic DROP COLUMN IF EXISTS node_type;
                ALTER TABLE knowledge_topic DROP COLUMN IF EXISTS graph_position;
                ALTER TABLE knowledge_topic DROP COLUMN IF EXISTS content_status;
            """,
        ),
    ]
