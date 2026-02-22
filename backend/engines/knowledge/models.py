"""
Knowledge Engine Models

Hierarchical structure: Program → Subject → Module → Topic
"""

import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings


class Program(models.Model):
    """
    Top-level exam program.
    Example: UPSC CSE, State PSC
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )
    name = models.CharField(
        max_length=100, unique=True, help_text="Program name (e.g., UPSC CSE)"
    )
    description = models.TextField(blank=True, help_text="Detailed description")
    exam_pattern = models.JSONField(
        default=dict, blank=True, help_text="Exam structure (prelims, mains, interview)"
    )
    is_active = models.BooleanField(
        default=True, help_text="Is this program currently active?"
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="Creation timestamp")
    updated_at = models.DateTimeField(auto_now=True, help_text="Last update timestamp")

    class Meta:
        db_table = "knowledge_program"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return self.name


class Subject(models.Model):
    """
    Subject within a program.
    Example: Polity, History, Geography
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )
    name = models.CharField(max_length=100, help_text="Subject name")
    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name="subjects",
        help_text="Parent program",
    )
    description = models.TextField(blank=True, help_text="Subject description")
    order_index = models.IntegerField(
        default=0, help_text="Display order within program"
    )
    is_active = models.BooleanField(default=True, help_text="Is this subject active?")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Creation timestamp")
    updated_at = models.DateTimeField(auto_now=True, help_text="Last update timestamp")

    class Meta:
        db_table = "knowledge_subject"
        ordering = ["program", "order_index", "name"]
        unique_together = [["program", "name"]]
        indexes = [
            models.Index(fields=["program", "order_index"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.program.name} - {self.name}"


class Module(models.Model):
    """
    Module/unit within a subject.
    Example: Fundamental Rights, Indian History
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )
    name = models.CharField(max_length=200, help_text="Module name")
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="modules",
        help_text="Parent subject",
    )
    description = models.TextField(blank=True, help_text="Module description")
    order_index = models.IntegerField(
        default=0, help_text="Display order within subject"
    )
    is_active = models.BooleanField(default=True, help_text="Is this module active?")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Creation timestamp")
    updated_at = models.DateTimeField(auto_now=True, help_text="Last update timestamp")

    class Meta:
        db_table = "knowledge_module"
        ordering = ["subject", "order_index", "name"]
        unique_together = [["subject", "name"]]
        indexes = [
            models.Index(fields=["subject", "order_index"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.subject.name} - {self.name}"


class Topic(models.Model):
    """
    Individual topic within a module.
    Can have parent-child relationships (sub-topics).
    """

    DIFFICULTY_CHOICES = [
        ("easy", "Easy"),
        ("medium", "Medium"),
        ("hard", "Hard"),
    ]

    TOPIC_TYPE_CHOICES = [
        ("syllabus", "Syllabus Topic"),
        ("custom", "Custom Topic"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )
    name = models.CharField(max_length=200, help_text="Topic name")
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name="topics",
        help_text="Parent module",
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="topics",
        help_text="Parent subject (for quick access)",
    )
    parent_topic = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="subtopics",
        null=True,
        blank=True,
        help_text="Parent topic (for sub-topics)",
    )
    description = models.TextField(blank=True, help_text="Detailed topic description")
    keywords = models.JSONField(
        default=list, blank=True, help_text="Keywords for AI mapping (list of strings)"
    )
    topic_type = models.CharField(
        max_length=20,
        choices=TOPIC_TYPE_CHOICES,
        default="syllabus",
        help_text="Topic classification",
    )
    difficulty_level = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default="medium",
        help_text="Difficulty level",
    )
    order_index = models.IntegerField(
        default=0, help_text="Display order within module"
    )
    is_active = models.BooleanField(default=True, help_text="Is this topic active?")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Creation timestamp")
    updated_at = models.DateTimeField(auto_now=True, help_text="Last update timestamp")

    class Meta:
        db_table = "knowledge_topic"
        ordering = ["module", "order_index", "name"]
        unique_together = [["module", "name"]]
        indexes = [
            models.Index(fields=["module", "order_index"]),
            models.Index(fields=["subject"]),
            models.Index(fields=["parent_topic"]),
            models.Index(fields=["difficulty_level"]),
            models.Index(fields=["topic_type"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        if self.parent_topic:
            return f"{self.parent_topic.name} → {self.name}"
        return f"{self.module.name} - {self.name}"


class ChunkTopicMap(models.Model):
    """
    Many-to-many mapping between chunks and topics.
    Tracks relevance score for ranking.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )
    chunk = models.ForeignKey(
        "content.Chunk",
        on_delete=models.CASCADE,
        related_name="topic_mappings",
        help_text="Source chunk",
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name="chunk_mappings",
        help_text="Target topic",
    )
    relevance_score = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Relevance score (0.0-1.0)",
    )
    priority = models.IntegerField(
        default=1, help_text="Priority level (1=basic, 2=intermediate, 3=advanced)"
    )
    auto_mapped = models.BooleanField(
        default=False, help_text="Was this mapping created automatically by AI?"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Admin who approved this mapping",
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="Creation timestamp")

    class Meta:
        db_table = "knowledge_chunk_topic_map"
        ordering = ["-relevance_score", "-priority"]
        unique_together = [["chunk", "topic"]]
        indexes = [
            models.Index(fields=["chunk"]),
            models.Index(fields=["topic"]),
            models.Index(fields=["topic", "-relevance_score"]),
            models.Index(fields=["auto_mapped"]),
        ]

    def __str__(self) -> str:
        return f"{self.topic.name} ← Chunk #{self.chunk.chunk_index} (score: {self.relevance_score:.2f})"


class Theme(models.Model):
    """
    Cross-cutting themes that span multiple topics.
    Example: Gender Equality, Climate Change
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )
    name = models.CharField(max_length=200, unique=True, help_text="Theme name")
    description = models.TextField(help_text="Theme description")
    topics: models.ManyToManyField = models.ManyToManyField(  # type: ignore
        Topic,
        through="ThemeTopicMap",
        related_name="themes",
        help_text="Topics included in this theme",
    )
    is_active = models.BooleanField(default=True, help_text="Is this theme active?")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Creation timestamp")
    updated_at = models.DateTimeField(auto_now=True, help_text="Last update timestamp")

    class Meta:
        db_table = "knowledge_theme"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return self.name


class ThemeTopicMap(models.Model):
    """
    Mapping between themes and topics with weight.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )
    theme = models.ForeignKey(Theme, on_delete=models.CASCADE, help_text="Parent theme")
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, help_text="Linked topic")
    weight = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Importance weight for this topic in the theme",
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="Creation timestamp")

    class Meta:
        db_table = "knowledge_theme_topic_map"
        unique_together = [["theme", "topic"]]
        ordering = ["-weight"]
        indexes = [
            models.Index(fields=["theme"]),
            models.Index(fields=["topic"]),
        ]

    def __str__(self) -> str:
        return f"{self.theme.name} → {self.topic.name} (weight: {self.weight})"


class ChunkRelation(models.Model):
    """
    Tracks relationships between chunks (duplicate, similar, expands).
    Used for deduplication in article generation.
    """

    RELATION_TYPE_CHOICES = [
        ("duplicate", "Duplicate"),
        ("similar", "Similar"),
        ("expands", "Expands On"),
        ("contradicts", "Contradicts"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )
    chunk_1 = models.ForeignKey(
        "content.Chunk",
        on_delete=models.CASCADE,
        related_name="relations_as_source",
        help_text="First chunk",
    )
    chunk_2 = models.ForeignKey(
        "content.Chunk",
        on_delete=models.CASCADE,
        related_name="relations_as_target",
        help_text="Second chunk",
    )
    relation_type = models.CharField(
        max_length=20, choices=RELATION_TYPE_CHOICES, help_text="Type of relationship"
    )
    similarity_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Similarity score (0.0-1.0)",
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="Creation timestamp")

    class Meta:
        db_table = "knowledge_chunk_relation"
        unique_together = [["chunk_1", "chunk_2"]]
        indexes = [
            models.Index(fields=["chunk_1"]),
            models.Index(fields=["chunk_2"]),
            models.Index(fields=["relation_type"]),
        ]

    def __str__(self) -> str:
        return f"Chunk {self.chunk_1.chunk_index} {self.relation_type} Chunk {self.chunk_2.chunk_index}"
