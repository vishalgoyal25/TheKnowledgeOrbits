"""
Book Content Engine — Models
Layer 1 (Book Content) + Layer 2 (Connections) + Layer 3 (Intelligence)

These models power the static UPSC book-quality article generation system.
Ported from POC: upsc-agent-lab/src/
DO NOT confuse with article_article (marketing tool) or assessment_* (quiz system).
"""

import uuid

import structlog
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models

logger = structlog.get_logger(__name__)


class BookPlan(models.Model):
    """
    Layer 1: Book Intelligence Plan.
    One plan per subject. Generated ONCE before article generation begins.
    Stores the AI-generated Table of Contents, concept registry,
    prerequisite chains, and reading order for the entire subject.
    Equivalent to POC's book_plans table.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this book plan.",
    )
    subject = models.OneToOneField(
        "knowledge.Subject",
        on_delete=models.CASCADE,
        related_name="book_plan",
        help_text="The subject this book plan belongs to.",
    )
    toc_json = models.JSONField(
        default=list,
        help_text=(
            "AI-generated complete Table of Contents. "
            "Structure: [{module, order, topics: [{name, subtopics, prerequisites}]}]"
        ),
    )
    concept_registry = models.JSONField(
        default=dict,
        help_text=(
            "Maps concept_name_lower → {topic_id (uuid), topic_label}. "
            "Updated after each article is generated. Powers Layer 3 cross-references."
        ),
    )
    prerequisite_chains = models.JSONField(
        default=dict,
        help_text=(
            "Maps topic_name → [prerequisite topic names]. "
            "Defines reading order for students."
        ),
    )
    reading_order = models.JSONField(
        default=list,
        help_text="Flat ordered list of topics for linear book-reading mode.",
    )
    generation_status = models.CharField(
        max_length=20,
        default="planned",
        help_text=(
            "Status of content generation for this subject. "
            "Values: planned | generating | partial | complete"
        ),
    )
    topics_planned = models.IntegerField(
        default=0,
        help_text="Total number of topic nodes planned in this subject's TOC.",
    )
    topics_completed = models.IntegerField(
        default=0,
        help_text="Number of topic nodes with generated book content.",
    )
    avg_quality_score = models.FloatField(
        default=0.0,
        help_text="Rolling average quality score across all generated articles in this subject.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this book plan was first created.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last time this book plan was updated.",
    )

    class Meta:
        db_table = "knowledge_book_plan"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["generation_status"],
                name="book_plan_status_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"BookPlan: {self.subject.name} ({self.generation_status})"


class BookContent(models.Model):
    """
    Layer 1: Generated book-quality article for a single topic node.
    One record per knowledge_topic node that has been generated.
    Stores the full Markdown article produced by the 3-Layer Quality Engine.
    This is the CORE output of the entire POC integration.
    Equivalent to POC's nodes.content_body field (but separated cleanly).
    DO NOT confuse with article_article — that is a separate marketing tool.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this book content entry.",
    )
    topic = models.OneToOneField(
        "knowledge.Topic",
        on_delete=models.CASCADE,
        related_name="book_content",
        help_text="The knowledge topic node this content belongs to.",
    )
    subject = models.ForeignKey(
        "knowledge.Subject",
        on_delete=models.CASCADE,
        related_name="book_contents",
        help_text="Denormalized subject FK for fast filtering without JOIN chain.",
    )
    content_markdown = models.TextField(
        help_text=(
            "Full generated Markdown article. "
            "Produced by Layer 2 Quality Engine (section-by-section generation)."
        ),
    )
    formatted_content = models.TextField(
        blank=True,
        default="",
        help_text=(
            "Phase 4.5B output: content WITH tables + callouts injected. "
            "Frontend renders this if available, falls back to content_markdown."
        ),
    )
    word_count = models.IntegerField(
        default=0,
        help_text="Word count of content_markdown. Computed on save.",
    )
    quality_score = models.FloatField(
        default=0.0,
        help_text=(
            "Self-critique quality score (0-100) from Layer 2. "
            "Articles below 65 are auto-refined before saving."
        ),
    )
    critique_log = models.TextField(
        blank=True,
        default="",
        help_text="Full JSON output of the self-critique pass. Audit trail.",
    )
    generation_pass = models.IntegerField(
        default=1,
        help_text="How many refinement passes the article took. 1=first pass passed.",
    )
    source_mode = models.CharField(
        max_length=30,
        default="wiki_only",
        help_text="Which sources were used. Values: wiki_only | ncert_wiki",
    )
    has_tables = models.BooleanField(
        default=False,
        help_text="Whether this article contains generated comparison/summary tables.",
    )
    has_media = models.BooleanField(
        default=False,
        help_text="Whether this article has image/infographic placeholders.",
    )
    is_published = models.BooleanField(
        default=False,
        help_text="Whether this content is visible to students.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this article was first generated.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last time this article was updated or refined.",
    )

    class Meta:
        db_table = "knowledge_book_content"
        ordering = ["-quality_score", "-created_at"]
        indexes = [
            models.Index(
                fields=["subject", "is_published"],
                name="book_content_subject_pub_idx",
            ),
            models.Index(
                fields=["quality_score"],
                name="book_content_quality_idx",
            ),
            models.Index(
                fields=["topic"],
                name="book_content_topic_idx",
            ),
            models.Index(
                fields=["source_mode"],
                name="book_content_source_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"BookContent: {self.topic.name} (score={self.quality_score:.0f})"

    def save(self, *args, **kwargs) -> None:
        """Auto-compute word count on save."""
        if self.content_markdown:
            self.word_count = len(self.content_markdown.split())
        super().save(*args, **kwargs)


class TopicRelation(models.Model):
    """
    Layer 2: Semantic relationship between two topic nodes.
    Powers the knowledge graph UI edges (related_to, cross_subject, prerequisite).
    Also powers the 'Related Topics' sidebar on article reader pages.
    Equivalent to POC's edges table WHERE relation='related_to'.
    The 'contains' hierarchy is already encoded in knowledge_topic.parent_topic_id FK.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this topic relation.",
    )
    source_topic = models.ForeignKey(
        "knowledge.Topic",
        on_delete=models.CASCADE,
        related_name="outgoing_relations",
        help_text="The source topic in this directional relationship.",
    )
    target_topic = models.ForeignKey(
        "knowledge.Topic",
        on_delete=models.CASCADE,
        related_name="incoming_relations",
        help_text="The target topic this relation points to.",
    )
    relation_type = models.CharField(
        max_length=30,
        default="related_to",
        help_text=(
            "Type of relationship. "
            "Values: related_to | prerequisite | cross_subject | contrast | applies_to"
        ),
    )
    similarity_score = models.FloatField(
        default=0.0,
        help_text=(
            "pgvector cosine similarity score (0.0-1.0). "
            "Populated by cross-linker after embeddings exist."
        ),
    )
    is_auto_detected = models.BooleanField(
        default=True,
        help_text="True=auto-detected by similarity engine. False=manually added.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this relation was created.",
    )

    class Meta:
        db_table = "knowledge_topic_relation"
        unique_together = [("source_topic", "target_topic")]
        ordering = ["-similarity_score"]
        indexes = [
            models.Index(
                fields=["source_topic", "relation_type"],
                name="topic_rel_source_type_idx",
            ),
            models.Index(
                fields=["target_topic"],
                name="topic_rel_target_idx",
            ),
            models.Index(
                fields=["relation_type"],
                name="topic_rel_type_idx",
            ),
            models.Index(
                fields=["relation_type"],
                name="topic_rel_cross_subject_idx",
                condition=models.Q(relation_type="cross_subject"),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.source_topic.name} →[{self.relation_type}]→ {self.target_topic.name}"


class CrossReference(models.Model):
    """
    Layer 2: Article-to-article cross-reference link.
    Injected by Layer 3 Coherence Engine after article generation.
    Powers the 'See Also' section at the bottom of every book article.
    Also powers the 'Related Articles' sidebar in the frontend reader.
    Equivalent to POC's cross_references table.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this cross-reference.",
    )
    source_content = models.ForeignKey(
        BookContent,
        on_delete=models.CASCADE,
        related_name="outgoing_references",
        help_text="The article that contains the reference.",
    )
    target_content = models.ForeignKey(
        BookContent,
        on_delete=models.CASCADE,
        related_name="incoming_references",
        help_text="The article being referenced.",
    )
    ref_type = models.CharField(
        max_length=30,
        default="see_also",
        help_text=(
            "Type of reference. "
            "Values: see_also | prerequisite | continuation | contrast"
        ),
    )
    ref_text = models.CharField(
        max_length=300,
        blank=True,
        default="",
        help_text="The concept phrase in the source article that triggered this reference.",
    )
    display_label = models.CharField(
        max_length=300,
        blank=True,
        default="",
        help_text=(
            "Human-readable link text shown to student. "
            "Example: 'Anti-Defection Law → Tenth Schedule'"
        ),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this cross-reference was injected.",
    )

    class Meta:
        db_table = "knowledge_cross_reference"
        unique_together = [("source_content", "target_content")]
        ordering = ["ref_type"]
        indexes = [
            models.Index(
                fields=["source_content"],
                name="crossref_source_idx",
            ),
            models.Index(
                fields=["target_content"],
                name="crossref_target_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"CrossRef: {self.source_content.topic.name} → {self.target_content.topic.name}"


class ContentMedia(models.Model):
    """
    Layer 1: Media asset linked to a book content article.
    Stores images, diagrams, infographic placeholders, and videos.
    Cloudinary-ready: cloudinary_url populated when asset is uploaded.
    Initially populated with placeholders from Phase 4.5B formatting pass.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this media asset.",
    )
    content = models.ForeignKey(
        BookContent,
        on_delete=models.CASCADE,
        related_name="media_assets",
        help_text="The book content article this media belongs to.",
    )
    media_type = models.CharField(
        max_length=30,
        help_text=(
            "Type of media. "
            "Values: image | diagram | table_image | infographic | video | placeholder"
        ),
    )
    cloudinary_url = models.TextField(
        blank=True,
        default="",
        help_text="Cloudinary CDN URL. Empty if placeholder not yet fulfilled.",
    )
    youtube_url = models.TextField(
        blank=True,
        default="",
        help_text="YouTube embed URL for video content.",
    )
    position = models.CharField(
        max_length=20,
        default="inline",
        help_text="Where in the article this media appears. Values: hero | inline | end",
    )
    position_marker = models.TextField(
        blank=True,
        default="",
        help_text=(
            "The exact marker string in content_markdown where this media is inserted. "
            "Example: '>[!infographic: Map of British India 1773]<' "
            "Frontend replaces this marker with the rendered component."
        ),
    )
    caption = models.TextField(
        blank=True,
        default="",
        help_text="Caption text displayed below the media.",
    )
    alt_text = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Accessibility alt text for images.",
    )
    display_order = models.IntegerField(
        default=0,
        help_text="Order of this media within the article.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this media asset was created.",
    )

    class Meta:
        db_table = "knowledge_content_media"
        ordering = ["display_order"]
        indexes = [
            models.Index(
                fields=["content", "display_order"],
                name="content_media_order_idx",
            ),
            models.Index(
                fields=["media_type"],
                name="content_media_type_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Media[{self.media_type}]: {self.content.topic.name}"


class GenerationLog(models.Model):
    """
    Layer 3: Tracks every book content generation run.
    Equivalent to POC's ingestion_logs table.
    Used for crash recovery, admin monitoring, and resumption logic.
    The management command reads this to implement Smart Skip.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this generation log entry.",
    )
    topic_name = models.CharField(
        max_length=500,
        help_text="Name of the topic being generated.",
    )
    subject_name = models.CharField(
        max_length=300,
        help_text="Name of the subject this topic belongs to.",
    )
    status = models.CharField(
        max_length=20,
        help_text="Outcome of this generation run. Values: success | failed | skipped",
    )
    nodes_created = models.IntegerField(
        default=0,
        help_text="Number of new BookContent records created in this run.",
    )
    relations_created = models.IntegerField(
        default=0,
        help_text="Number of new TopicRelation records created in this run.",
    )
    cross_refs_created = models.IntegerField(
        default=0,
        help_text="Number of CrossReference records injected in this run.",
    )
    quality_score = models.FloatField(
        default=0.0,
        help_text="Quality score of the generated article (0-100).",
    )
    word_count = models.IntegerField(
        default=0,
        help_text="Word count of the generated article.",
    )
    error_message = models.TextField(
        blank=True,
        default="",
        help_text="Full error message if status=failed.",
    )
    generation_time_seconds = models.IntegerField(
        default=0,
        help_text="Total wall-clock seconds taken for this generation run.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this log entry was created (= when generation ran).",
    )

    class Meta:
        db_table = "knowledge_generation_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["status", "-created_at"],
                name="gen_log_status_time_idx",
            ),
            models.Index(
                fields=["subject_name"],
                name="gen_log_subject_idx",
            ),
            models.Index(
                fields=["topic_name"],
                name="gen_log_topic_idx",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"GenLog: {self.topic_name} [{self.status}] score={self.quality_score:.0f}"
        )


class BookChunk(models.Model):
    """
    Phase E — Hybrid RAG Infrastructure.

    One chunk (~1200 chars) of a generated BookContent article.
    Separate from content_chunk (NCERT/PDFs) and ca_chunk (Current Affairs).
    Each source type owns its chunk table — never mixed.

    Two embedding namespaces in content_embedding (universal table):
      content_type="book_chunk"   → this chunk's vector  (RAG precision)
      content_type="book_article" → parent article vector (similarity speed)

    Topic mapping is implicit via FK chain:
      BookChunk → BookContent.topic → knowledge.Topic
    No separate ChunkTopicMap needed for book content.

    source_type is extensible — adding govt/news sources later requires
    only a new string value, zero schema migration needed.
    """

    SOURCE_TYPE_CHOICES = [
        ("wiki",       "Wikipedia"),
        ("govt",       "Government Source"),
        ("news",       "News Source"),
        ("ncert_blend","NCERT + Wiki Blend"),
        ("mixed",      "Multiple Sources"),
    ]

    QUALITY_FLAG_CHOICES = [
        ("high",         "High Quality"),
        ("medium",       "Medium Quality"),
        ("low",          "Low Quality"),
        ("needs_review", "Needs Review"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this book chunk.",
    )
    book_content = models.ForeignKey(
        BookContent,
        on_delete=models.CASCADE,
        related_name="chunks",
        help_text=(
            "The BookContent article this chunk belongs to. "
            "Topic link is implicit: BookChunk → BookContent → Topic."
        ),
    )
    chunk_text = models.TextField(
        help_text="~1200-character semantic chunk of the parent article.",
    )
    chunk_index = models.IntegerField(
        help_text="Zero-based position of this chunk within the parent article.",
    )
    source_type = models.CharField(
        max_length=30,
        default="wiki",
        choices=SOURCE_TYPE_CHOICES,
        help_text=(
            "Origin of the source material used to generate this chunk. "
            "Adding new sources (govt, news) requires only a new string value — "
            "no migration needed."
        ),
    )
    quality_flag = models.CharField(
        max_length=20,
        default="high",
        choices=QUALITY_FLAG_CHOICES,
        help_text="Quality assessment from ChunkingService._assess_quality().",
    )
    search_vector = SearchVectorField(
        null=True,
        help_text=(
            "PostgreSQL tsvector for BM25 full-text search (keyword matching). "
            "Populated on save via SearchVector(chunk_text, config='english'). "
            "Indexed with GIN for sub-millisecond keyword queries. "
            "Part of the Hybrid RAG pipeline: BM25 + semantic vector."
        ),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this chunk was created.",
    )

    class Meta:
        db_table = "knowledge_book_chunk"
        unique_together = [("book_content", "chunk_index")]
        ordering = ["book_content", "chunk_index"]
        indexes = [
            # BM25 keyword search — fast even at 500k rows
            GinIndex(
                fields=["search_vector"],
                name="book_chunk_fts_idx",
            ),
            # Filter by source type (wiki / govt / news)
            models.Index(
                fields=["source_type"],
                name="book_chunk_source_idx",
            ),
            # Retrieve all chunks for an article in order
            models.Index(
                fields=["book_content", "chunk_index"],
                name="book_chunk_content_order_idx",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"BookChunk[{self.chunk_index}]: "
            f"{self.book_content.topic.name} ({self.source_type})"
        )
