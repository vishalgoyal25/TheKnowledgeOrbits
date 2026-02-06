"""
Content Engine Models

Responsibility: Store and manage all ingested content (PDFs, web, text) as chunks.
Principle: Chunks are the foundation. Articles are generated from chunks, never stored raw.
"""
import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Document(models.Model):
    """
    Represents a source document (PDF, web article, book).
    
    Documents are chunked into smaller pieces for semantic processing.
    Supports versioning for NCERT editions and reference book updates.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the document"
    )
    
    title = models.CharField(
        max_length=500,
        help_text="Document title (e.g., 'NCERT Class 12 Polity')"
    )
    
    file_path = models.TextField(
        help_text="Storage path or URL to the original file"
    )
    
    source_type = models.CharField(
        max_length=50,
        choices=[
            ('static', 'Static Content (NCERT, Books)'),
            ('dynamic', 'Dynamic Content (Web, News)')
        ],
        help_text="Content category for retrieval strategy"
    )
    
    # Versioning fields
    source_edition = models.CharField(
        max_length=50,
        blank=True,
        help_text="Edition identifier (e.g., 'NCERT 2024', 'Laxmikanth 6th Ed')"
    )
    
    source_version = models.CharField(
        max_length=20,
        blank=True,
        help_text="Version number (e.g., '1.0', '2.1')"
    )
    
    isbn = models.CharField(
        max_length=20,
        blank=True,
        help_text="ISBN for books"
    )
    
    publication_year = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1900), MaxValueValidator(2100)],
        help_text="Year of publication"
    )
    
    # Relations (will link to Knowledge Engine's Subject model in Phase 1 Week 3)
    # For now, this is nullable to avoid circular dependency
    # subject_id will be added as ForeignKey when Knowledge Engine is built
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (author, publisher, tags, etc.)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Document upload timestamp"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last modification timestamp"
    )
    
    class Meta:
        db_table = 'content_document'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['source_type']),
            models.Index(fields=['source_edition']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'
    
    def __str__(self) -> str:
        return f"{self.title} ({self.source_edition or 'No Edition'})"


class Chunk(models.Model):
    """
    Represents a semantic chunk of text (~1200 characters).
    
    Core principle: All content is stored as chunks.
    Articles and quizzes are GENERATED from chunks via RAG, never stored directly.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the chunk"
    )
    
    chunk_text = models.TextField(
        help_text="The actual text content of the chunk (~1200 characters)"
    )
    
    chunk_index = models.IntegerField(
        help_text="Sequential index within the document (0, 1, 2...)"
    )
    
    page_number = models.IntegerField(
        null=True,
        blank=True,
        help_text="Source page number (for PDFs)"
    )
    
    source_type = models.CharField(
        max_length=50,
        choices=[
            ('static', 'Static Content'),
            ('dynamic', 'Dynamic Content (Current Affairs)')
        ],
        help_text="Matches parent document's source_type for efficient filtering"
    )
    
    # Relations
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='chunks',
        help_text="Parent document this chunk belongs to"
    )
    
    # Context metadata
    chapter_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Chapter/section name extracted from document structure"
    )
    
    # Quality indicators
    quality_flag = models.CharField(
        max_length=20,
        choices=[
            ('high', 'High Quality'),
            ('medium', 'Medium Quality'),
            ('low', 'Low Quality'),
            ('needs_review', 'Needs Review')
        ],
        default='high',
        help_text="Quality assessment of chunk extraction"
    )
    
    confidence_score = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="OCR or extraction confidence (0.0 to 1.0)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Chunk creation timestamp"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last modification timestamp"
    )
    
    class Meta:
        db_table = 'content_chunk'
        ordering = ['document', 'chunk_index']
        indexes = [
            models.Index(fields=['document', 'chunk_index']),
            models.Index(fields=['source_type']),
            models.Index(fields=['chapter_name']),
            models.Index(fields=['quality_flag']),
        ]
        unique_together = [['document', 'chunk_index']]
        verbose_name = 'Chunk'
        verbose_name_plural = 'Chunks'
    
    def __str__(self) -> str:
        return f"Chunk {self.chunk_index} from {self.document.title}"


class Embedding(models.Model):
    """
    Stores vector embeddings for semantic search.
    
    Uses pgvector extension for efficient similarity search.
    Model: sentence-transformers (all-MiniLM-L6-v2), 384 dimensions.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the embedding"
    )
    
    content_type = models.CharField(
        max_length=50,
        choices=[
            ('chunk', 'Chunk Embedding'),
            ('article', 'Article Embedding (future)'),
            ('question', 'Question Embedding (future)')
        ],
        help_text="Type of content being embedded"
    )
    
    content_id = models.UUIDField(
        help_text="UUID of the content (chunk_id, article_id, etc.)"
    )
    
    # Vector field - requires pgvector extension
    # Format: array of 384 floats
    # Note: In actual implementation, use pgvector's VectorField
    # For now, storing as JSONField to avoid pgvector dependency in models
    vector = models.JSONField(
        help_text="384-dimensional embedding vector (stored as JSON array)"
    )
    
    model_name = models.CharField(
        max_length=100,
        default='all-MiniLM-L6-v2',
        help_text="Embedding model used for generation"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Embedding generation timestamp"
    )
    
    class Meta:
        db_table = 'content_embedding'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['content_type', 'content_id']),
            # pgvector index will be added via migration:
            # CREATE INDEX idx_embedding_vector ON content_embedding 
            # USING ivfflat (vector vector_cosine_ops);
        ]
        unique_together = [['content_type', 'content_id']]
        verbose_name = 'Embedding'
        verbose_name_plural = 'Embeddings'
    
    def __str__(self) -> str:
        return f"{self.content_type} embedding for {self.content_id}"


class Asset(models.Model):
    """
    Stores extracted assets (tables, diagrams, formulas) from documents.
    
    Phase 1: PLACEHOLDER ONLY - Not used in MVP.
    Reason: Text-only approach for Phase 1 (avoid over-engineering).
    Will be implemented in Phase 8+ (Advanced Content Engine).
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the asset"
    )
    
    chunk = models.ForeignKey(
        Chunk,
        on_delete=models.CASCADE,
        related_name='assets',
        help_text="Parent chunk this asset belongs to"
    )
    
    asset_type = models.CharField(
        max_length=50,
        choices=[
            ('table', 'Table'),
            ('diagram', 'Diagram/Image'),
            ('formula', 'Mathematical Formula')
        ],
        help_text="Type of extracted asset"
    )
    
    asset_url = models.TextField(
        blank=True,
        help_text="CDN URL or file path to the asset"
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Asset-specific metadata (dimensions, format, etc.)"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Asset extraction timestamp"
    )
    
    class Meta:
        db_table = 'content_asset'
        ordering = ['chunk', 'asset_type']
        indexes = [
            models.Index(fields=['chunk']),
            models.Index(fields=['asset_type']),
        ]
        verbose_name = 'Asset'
        verbose_name_plural = 'Assets'
    
    def __str__(self) -> str:
        return f"{self.asset_type} for {self.chunk}"


class IngestionJob(models.Model):
    """
    Tracks the status of document ingestion jobs.
    
    Purpose: Monitor async PDF processing (upload → extract → chunk → embed).
    Supports retry logic and error tracking.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the ingestion job"
    )
    
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='ingestion_jobs',
        null=True,
        blank=True,
        help_text="Document being processed (null if job failed before document creation)"
    )
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed')
        ],
        default='pending',
        help_text="Current job status"
    )
    
    error_log = models.TextField(
        blank=True,
        help_text="Error messages if job failed"
    )
    
    # Progress tracking
    total_pages = models.IntegerField(
        null=True,
        blank=True,
        help_text="Total pages in document (for progress calculation)"
    )
    
    processed_pages = models.IntegerField(
        default=0,
        help_text="Pages processed so far"
    )
    
    chunks_created = models.IntegerField(
        default=0,
        help_text="Number of chunks created"
    )
    
    # Timestamps
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Job start timestamp"
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Job completion timestamp"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Job creation timestamp"
    )
    
    class Meta:
        db_table = 'content_ingestion_job'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['document']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Ingestion Job'
        verbose_name_plural = 'Ingestion Jobs'
    
    def __str__(self) -> str:
        doc_name = self.document.title if self.document else "Unknown Document"
        return f"{self.status.upper()}: {doc_name}"
    
    @property
    def progress_percentage(self) -> float:
        """Calculate job progress as percentage."""
        if not self.total_pages or self.total_pages == 0:
            return 0.0
        return (self.processed_pages / self.total_pages) * 100
    
    