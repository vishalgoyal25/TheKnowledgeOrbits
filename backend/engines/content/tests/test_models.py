"""
Content Engine Model Tests

Tests for Document, Chunk, Embedding, Asset, and IngestionJob models.
Target: 90% model coverage.
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from engines.content.models import Document, Chunk, Asset, IngestionJob
from engines.content.tests.factories import (
    DocumentFactory,
    ChunkFactory,
    EmbeddingFactory,
    AssetFactory,
    IngestionJobFactory,
)


# ============================================================================
# DOCUMENT MODEL TESTS
# ============================================================================


@pytest.mark.django_db
class TestDocumentModel:
    """Test suite for Document model."""

    def test_document_creation_with_required_fields(self):
        """Test document creation with only required fields."""
        # ARRANGE & ACT
        document = DocumentFactory(
            title="NCERT Class 12 Polity",
            file_path="/media/ncert_polity.pdf",
            source_type="static",
        )

        # ASSERT
        assert document.id is not None
        assert document.title == "NCERT Class 12 Polity"
        assert document.source_type == "static"
        assert document.created_at is not None
        assert document.updated_at is not None

    def test_document_creation_with_all_fields(self):
        """Test document creation with all fields populated."""
        # ARRANGE & ACT
        document = DocumentFactory(
            title="Laxmikanth Polity",
            source_edition="6th Edition",
            source_version="2.0",
            isbn="9788193506066",
            publication_year=2024,
        )

        # ASSERT
        assert document.source_edition == "6th Edition"
        assert document.source_version == "2.0"
        assert document.isbn == "9788193506066"
        assert document.publication_year == 2024

    def test_document_str_representation(self):
        """Test document __str__ method."""
        # ARRANGE
        document = DocumentFactory(title="Test Document", source_edition="2024")

        # ACT
        result = str(document)

        # ASSERT
        assert "Test Document" in result
        assert "2024" in result

    def test_document_str_without_edition(self):
        """Test document __str__ when no edition provided."""
        # ARRANGE
        document = DocumentFactory(title="Test Document", source_edition="")

        # ACT
        result = str(document)

        # ASSERT
        assert "Test Document" in result
        assert "No Edition" in result

    def test_document_metadata_default_is_dict(self):
        """Test that metadata defaults to empty dict."""
        # ARRANGE & ACT
        document = DocumentFactory(metadata={})

        # ASSERT
        assert isinstance(document.metadata, dict)
        assert document.metadata == {}

    def test_document_ordering_by_created_at_desc(self):
        """Test documents are ordered by created_at descending."""
        # ARRANGE
        doc1 = DocumentFactory(title="First")
        doc2 = DocumentFactory(title="Second")
        doc3 = DocumentFactory(title="Third")

        # ACT
        documents = Document.objects.all()

        # ASSERT
        assert documents[0] == doc3  # Most recent first
        assert documents[1] == doc2
        assert documents[2] == doc1

    def test_document_publication_year_validation_min(self):
        """Test publication year cannot be before 1900."""
        # ARRANGE
        document = DocumentFactory.build(publication_year=1899)

        # ACT & ASSERT
        with pytest.raises(ValidationError):
            document.full_clean()

    def test_document_publication_year_validation_max(self):
        """Test publication year cannot be after 2100."""
        # ARRANGE
        document = DocumentFactory.build(publication_year=2101)

        # ACT & ASSERT
        with pytest.raises(ValidationError):
            document.full_clean()


# ============================================================================
# CHUNK MODEL TESTS
# ============================================================================


@pytest.mark.django_db
class TestChunkModel:
    """Test suite for Chunk model."""

    def test_chunk_creation_with_required_fields(self):
        """Test chunk creation with required fields."""
        # ARRANGE
        document = DocumentFactory()

        # ACT
        chunk = ChunkFactory(
            document=document,
            chunk_text="This is a test chunk.",
            chunk_index=0,
            source_type="static",
        )

        # ASSERT
        assert chunk.id is not None
        assert chunk.document == document
        assert chunk.chunk_text == "This is a test chunk."
        assert chunk.chunk_index == 0

    def test_chunk_belongs_to_document(self):
        """Test chunk-document relationship."""
        # ARRANGE
        document = DocumentFactory()
        chunk1 = ChunkFactory(document=document, chunk_index=0)
        chunk2 = ChunkFactory(document=document, chunk_index=1)

        # ACT
        chunks = document.chunks.all()

        # ASSERT
        assert chunks.count() == 2
        assert chunk1 in chunks
        assert chunk2 in chunks

    def test_chunk_cascade_delete_with_document(self):
        """Test chunks are deleted when document is deleted."""
        # ARRANGE
        document = DocumentFactory()
        ChunkFactory(document=document, chunk_index=0)
        ChunkFactory(document=document, chunk_index=1)

        chunk_count_before = Chunk.objects.count()

        # ACT
        document.delete()

        # ASSERT
        chunk_count_after = Chunk.objects.count()
        assert chunk_count_before == 2
        assert chunk_count_after == 0

    def test_chunk_unique_together_document_and_index(self):
        """Test chunk (document, chunk_index) must be unique."""
        # ARRANGE
        document = DocumentFactory()
        ChunkFactory(document=document, chunk_index=0)

        # ACT & ASSERT
        with pytest.raises(IntegrityError):
            ChunkFactory(document=document, chunk_index=0)

    def test_chunk_str_representation(self):
        """Test chunk __str__ method."""
        # ARRANGE
        document = DocumentFactory(title="Test Doc")
        chunk = ChunkFactory(document=document, chunk_index=5)

        # ACT
        result = str(chunk)

        # ASSERT
        assert "Chunk 5" in result
        assert "Test Doc" in result

    def test_chunk_quality_flag_default_is_high(self):
        """Test quality_flag defaults to 'high'."""
        # ARRANGE & ACT
        chunk = ChunkFactory()

        # ASSERT
        assert chunk.quality_flag == "high"

    def test_chunk_confidence_score_default_is_1(self):
        """Test confidence_score defaults to 1.0."""
        # ARRANGE & ACT
        chunk = ChunkFactory()

        # ASSERT
        assert chunk.confidence_score == 1.0

    def test_chunk_confidence_score_validation_min(self):
        """Test confidence_score cannot be negative."""
        # ARRANGE
        chunk = ChunkFactory.build(confidence_score=-0.1)

        # ACT & ASSERT
        with pytest.raises(ValidationError):
            chunk.full_clean()

    def test_chunk_confidence_score_validation_max(self):
        """Test confidence_score cannot exceed 1.0."""
        # ARRANGE
        chunk = ChunkFactory.build(confidence_score=1.1)

        # ACT & ASSERT
        with pytest.raises(ValidationError):
            chunk.full_clean()

    def test_chunk_ordering_by_document_and_index(self):
        """Test chunks ordered by document then chunk_index."""
        # ARRANGE
        doc = DocumentFactory()
        chunk2 = ChunkFactory(document=doc, chunk_index=2)
        chunk0 = ChunkFactory(document=doc, chunk_index=0)
        chunk1 = ChunkFactory(document=doc, chunk_index=1)

        # ACT
        chunks = Chunk.objects.filter(document=doc)

        # ASSERT
        assert list(chunks) == [chunk0, chunk1, chunk2]


# ============================================================================
# EMBEDDING MODEL TESTS
# ============================================================================


@pytest.mark.django_db
class TestEmbeddingModel:
    """Test suite for Embedding model."""

    def test_embedding_creation_for_chunk(self):
        """Test embedding creation for chunk content."""
        # ARRANGE
        chunk = ChunkFactory()

        # ACT
        embedding = EmbeddingFactory(content_type="chunk", content_id=chunk.id)

        # ASSERT
        assert embedding.id is not None
        assert embedding.content_type == "chunk"
        assert embedding.content_id == chunk.id
        assert len(embedding.vector) == 384

    def test_embedding_vector_is_384_dimensions(self):
        """Test embedding vector has 384 dimensions."""
        # ARRANGE & ACT
        embedding = EmbeddingFactory()

        # ASSERT
        assert isinstance(embedding.vector, list)
        assert len(embedding.vector) == 384

    def test_embedding_model_name_default(self):
        """Test model_name defaults to sentence-transformers model."""
        # ARRANGE & ACT
        embedding = EmbeddingFactory()

        # ASSERT
        assert embedding.model_name == "all-MiniLM-L6-v2"

    def test_embedding_unique_together_content_type_and_id(self):
        """Test (content_type, content_id) must be unique."""
        # ARRANGE
        chunk = ChunkFactory()
        EmbeddingFactory(content_type="chunk", content_id=chunk.id)

        # ACT & ASSERT
        with pytest.raises(IntegrityError):
            EmbeddingFactory(content_type="chunk", content_id=chunk.id)

    def test_embedding_str_representation(self):
        """Test embedding __str__ method."""
        # ARRANGE
        chunk = ChunkFactory()
        embedding = EmbeddingFactory(content_type="chunk", content_id=chunk.id)

        # ACT
        result = str(embedding)

        # ASSERT
        assert "chunk" in result
        assert str(chunk.id) in result


# ============================================================================
# ASSET MODEL TESTS
# ============================================================================


@pytest.mark.django_db
class TestAssetModel:
    """Test suite for Asset model (placeholder for Phase 1)."""

    def test_asset_creation(self):
        """Test asset creation linked to chunk."""
        # ARRANGE
        chunk = ChunkFactory()

        # ACT
        asset = AssetFactory(chunk=chunk, asset_type="table")

        # ASSERT
        assert asset.id is not None
        assert asset.chunk == chunk
        assert asset.asset_type == "table"

    def test_asset_belongs_to_chunk(self):
        """Test asset-chunk relationship."""
        # ARRANGE
        chunk = ChunkFactory()
        asset1 = AssetFactory(chunk=chunk, asset_type="table")
        asset2 = AssetFactory(chunk=chunk, asset_type="diagram")

        # ACT
        assets = chunk.assets.all()

        # ASSERT
        assert assets.count() == 2
        assert asset1 in assets
        assert asset2 in assets

    def test_asset_cascade_delete_with_chunk(self):
        """Test assets deleted when chunk is deleted."""
        # ARRANGE
        chunk = ChunkFactory()
        AssetFactory(chunk=chunk)
        AssetFactory(chunk=chunk)

        asset_count_before = Asset.objects.count()

        # ACT
        chunk.delete()

        # ASSERT
        asset_count_after = Asset.objects.count()
        assert asset_count_before == 2
        assert asset_count_after == 0

    def test_asset_str_representation(self):
        """Test asset __str__ method."""
        # ARRANGE
        chunk = ChunkFactory()
        asset = AssetFactory(chunk=chunk, asset_type="diagram")

        # ACT
        result = str(asset)

        # ASSERT
        assert "diagram" in result


# ============================================================================
# INGESTION JOB MODEL TESTS
# ============================================================================


@pytest.mark.django_db
class TestIngestionJobModel:
    """Test suite for IngestionJob model."""

    def test_ingestion_job_creation(self):
        """Test ingestion job creation."""
        # ARRANGE
        document = DocumentFactory()

        # ACT
        job = IngestionJobFactory(document=document, status="pending", total_pages=100)

        # ASSERT
        assert job.id is not None
        assert job.document == document
        assert job.status == "pending"
        assert job.total_pages == 100

    def test_ingestion_job_default_status_is_pending(self):
        """Test status defaults to 'pending'."""
        # ARRANGE & ACT
        job = IngestionJobFactory()

        # ASSERT
        assert job.status == "pending"

    def test_ingestion_job_progress_percentage_calculation(self):
        """Test progress_percentage property calculates correctly."""
        # ARRANGE
        job = IngestionJobFactory(total_pages=100, processed_pages=50)

        # ACT
        progress = job.progress_percentage

        # ASSERT
        assert progress == 50.0

    def test_ingestion_job_progress_percentage_zero_when_no_total(self):
        """Test progress_percentage returns 0 when total_pages is 0."""
        # ARRANGE
        job = IngestionJobFactory(total_pages=0, processed_pages=0)

        # ACT
        progress = job.progress_percentage

        # ASSERT
        assert progress == 0.0

    def test_ingestion_job_progress_percentage_complete(self):
        """Test progress_percentage returns 100 when complete."""
        # ARRANGE
        job = IngestionJobFactory(total_pages=100, processed_pages=100)

        # ACT
        progress = job.progress_percentage

        # ASSERT
        assert progress == 100.0

    def test_ingestion_job_str_representation_with_document(self):
        """Test __str__ with document attached."""
        # ARRANGE
        document = DocumentFactory(title="Test PDF")
        job = IngestionJobFactory(document=document, status="processing")

        # ACT
        result = str(job)

        # ASSERT
        assert "PROCESSING" in result
        assert "Test PDF" in result

    def test_ingestion_job_str_representation_without_document(self):
        """Test __str__ without document (failed before creation)."""
        # ARRANGE
        job = IngestionJobFactory(document=None, status="failed")

        # ACT
        result = str(job)

        # ASSERT
        assert "FAILED" in result
        assert "Unknown Document" in result

    def test_ingestion_job_cascade_delete_with_document(self):
        """Test jobs deleted when document is deleted."""
        # ARRANGE
        document = DocumentFactory()
        IngestionJobFactory(document=document)
        IngestionJobFactory(document=document)

        job_count_before = IngestionJob.objects.count()

        # ACT
        document.delete()

        # ASSERT
        job_count_after = IngestionJob.objects.count()
        assert job_count_before == 2
        assert job_count_after == 0
