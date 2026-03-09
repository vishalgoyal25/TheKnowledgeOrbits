"""
Current Affairs Engine - Models

Tables:
- CASource: RSS feed sources
- CAArticle: Raw news articles
- CAChunk: Processed CA chunks
- CATopicLink: CA chunk to topic mapping
"""

import uuid
from datetime import timedelta
from typing import Any

from django.db import models


class CASource(models.Model):
    """RSS feed sources for current affairs"""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )
    name = models.CharField(max_length=200, help_text="Source name (e.g., 'The Hindu')")
    source_type = models.CharField(
        max_length=50, default="rss", help_text="Source type (rss, api, manual)"
    )
    url = models.URLField(max_length=500, help_text="RSS feed URL")
    is_active = models.BooleanField(
        default=True, help_text="Whether to scrape this source"
    )
    scrape_frequency = models.CharField(
        max_length=20,
        default="daily",
        choices=[
            ("hourly", "Hourly"),
            ("daily", "Daily"),
            ("weekly", "Weekly"),
        ],
        help_text="How often to scrape",
    )
    last_scraped_at = models.DateTimeField(
        null=True, blank=True, help_text="Last successful scrape timestamp"
    )
    last_error = models.TextField(
        blank=True, default="", help_text="Last scraping error (if any)"
    )
    article_count = models.IntegerField(
        default=0, help_text="Total articles scraped from this source"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ca_source"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["last_scraped_at"]),
        ]

    def __str__(self) -> Any:
        return f"{self.name} ({self.source_type})"


class CAArticle(models.Model):
    """Raw current affairs articles from sources"""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )
    source = models.ForeignKey(
        CASource,
        on_delete=models.CASCADE,
        related_name="articles",
        help_text="Source this article came from",
    )
    title = models.CharField(max_length=500, help_text="Article title")
    url = models.URLField(
        max_length=1000, unique=True, help_text="Article URL (must be unique)"
    )
    content = models.TextField(help_text="Full article content")
    summary = models.TextField(
        blank=True, default="", help_text="Article summary (if available)"
    )
    published_at = models.DateTimeField(help_text="Publication timestamp from source")
    author = models.CharField(
        max_length=200, blank=True, default="", help_text="Article author"
    )
    categories = models.JSONField(default=list, help_text="Article categories/tags")

    # Processing status
    processing_status = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        help_text="Processing status",
    )
    processing_error = models.TextField(
        blank=True, default="", help_text="Processing error (if failed)"
    )
    processed_at = models.DateTimeField(
        null=True, blank=True, help_text="When processing completed"
    )

    # Metadata
    word_count = models.IntegerField(default=0, help_text="Article word count")
    chunk_count = models.IntegerField(default=0, help_text="Number of chunks generated")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ca_article"
        ordering = ["-published_at"]
        indexes = [
            models.Index(fields=["source", "-published_at"]),
            models.Index(fields=["processing_status"]),
            models.Index(fields=["-published_at"]),
            models.Index(fields=["source", "processing_status"]),
        ]

    def save(self, *args, **kwargs) -> Any:  # type: ignore
        """Auto-generate summary if not provided"""
        if (not self.summary or self.summary == "") and self.content:
            self.summary = (
                (self.content[:150] + "...")
                if len(self.content) > 150
                else self.content
            )
        super().save(*args, **kwargs)

    def __str__(self) -> Any:
        return self.title


class CAChunk(models.Model):
    """Processed CA chunks (same structure as static chunks)"""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )
    ca_article = models.ForeignKey(
        CAArticle,
        on_delete=models.CASCADE,
        related_name="chunks",
        help_text="CA article this chunk belongs to",
    )
    chunk_text = models.TextField(help_text="Chunk content (~1200 chars)")
    chunk_index = models.IntegerField(help_text="Sequential chunk index within article")

    # Source tracking
    source_type = models.CharField(
        max_length=50, default="dynamic", help_text="Always 'dynamic' for CA chunks"
    )

    # Time management
    published_at = models.DateTimeField(help_text="Original article publication date")
    expiry_date = models.DateTimeField(
        help_text="When this chunk becomes stale (published_at + 180 days)"
    )
    is_expired = models.BooleanField(
        default=False, help_text="Whether this chunk has expired"
    )

    # Quality metrics
    quality_flag = models.CharField(
        max_length=20,
        default="medium",
        choices=[
            ("high", "High"),
            ("medium", "Medium"),
            ("low", "Low"),
            ("needs_review", "Needs Review"),
        ],
        help_text="Quality assessment",
    )
    confidence_score = models.FloatField(
        default=0.7, help_text="Confidence score (0-1)"
    )

    # Embedding reference
    embedding_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Reference to embedding in content_embedding table",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ca_chunk"
        ordering = ["ca_article", "chunk_index"]
        indexes = [
            models.Index(fields=["ca_article", "chunk_index"]),
            models.Index(fields=["published_at"]),
            models.Index(fields=["expiry_date"]),
            models.Index(fields=["is_expired"]),
            models.Index(fields=["source_type"]),
        ]

    def save(self, *args, **kwargs) -> Any:  # type: ignore
        """Auto-set expiry_date if not set"""
        if not self.expiry_date and self.published_at:
            self.expiry_date = self.published_at + timedelta(days=180)
        super().save(*args, **kwargs)

    def __str__(self) -> Any:
        return f"CA Chunk {self.chunk_index} from {self.ca_article.title[:50]}"


class CATopicLink(models.Model):
    """Links CA chunks to syllabus topics"""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )
    ca_chunk = models.ForeignKey(
        CAChunk,
        on_delete=models.CASCADE,
        related_name="topic_links",
        help_text="CA chunk",
    )
    topic = models.ForeignKey(
        "knowledge.Topic",
        on_delete=models.CASCADE,
        related_name="ca_links",
        help_text="Linked topic",
    )
    relevance_score = models.FloatField(
        default=1.0, help_text="How relevant this chunk is to topic (0-1)"
    )
    link_method = models.CharField(
        max_length=20,
        default="auto",
        choices=[
            ("auto", "Auto-linked (AI)"),
            ("manual", "Manual (Admin)"),
        ],
        help_text="How this link was created",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ca_topic_link"
        ordering = ["-relevance_score"]
        unique_together = ["ca_chunk", "topic"]
        indexes = [
            models.Index(fields=["ca_chunk"]),
            models.Index(fields=["topic"]),
            models.Index(fields=["relevance_score"]),
        ]

    def __str__(self) -> Any:
        return f"{self.ca_chunk.ca_article.title[:30]} → {self.topic.name}"
