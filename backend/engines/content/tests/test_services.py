"""
Content Engine Services Tests

Tests for ChunkingService, EmbeddingService, and IngestionService.
Target: 85% service coverage.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.core.files.uploadedfile import SimpleUploadedFile

from engines.content.services.chunking_service import ChunkingService
from engines.content.services.embedding_service import EmbeddingService
from engines.content.services.ingestion_service import IngestionService
from engines.content.models import Document, Chunk, Embedding, IngestionJob
from engines.content.tests.factories import DocumentFactory, ChunkFactory


# ============================================================================
# CHUNKING SERVICE TESTS
# ============================================================================


class TestChunkingService:
    """Test suite for ChunkingService."""

    # 500+ chars realistic text for testing
    TEST_TEXT = (
        "India is a sovereign, socialist, secular, democratic republic, assuring its citizens justice, equality, "
        "and liberty, and endeavors to promote fraternity. The Constitution of India was adopted by the Constituent "
        "Assembly on 26 November 1949 and came into effect on 26 January 1950. Dr. B. R. Ambedkar was the chairman "
        "of the drafting committee. The constitution declares India a sovereign, socialist, secular, and democratic "
        "republic, assures its citizens justice, equality, and liberty, and endeavors to promote fraternity. "
        "It is the longest written constitution of any country on earth."
    )

    def test_chunk_text_creates_chunks_from_simple_text(self):
        """Test chunking creates proper chunks from text."""
        # ARRANGE
        text = self.TEST_TEXT * 5  # Make it long enough for multiple chunks
        document_id = "test-doc-id"

        # ACT
        chunks = ChunkingService.chunk_text(
            text=text, document_id=document_id, page_number=1
        )

        # ASSERT
        assert len(chunks) > 0
        assert all("chunk_text" in c for c in chunks)
        assert all("chunk_index" in c for c in chunks)
        assert chunks[0]["document_id"] == document_id

    def test_chunk_text_respects_chunk_size_limit(self):
        """Test chunks are approximately 1200 characters."""
        # ARRANGE
        text = self.TEST_TEXT * 10  # ~5000 chars

        # ACT
        chunks = ChunkingService.chunk_text(
            text=text, document_id="test-id", page_number=1
        )

        # ASSERT
        for chunk in chunks:
            chunk_length = len(chunk["chunk_text"])
            # Allow variance but ensure it respects min size (300) and isn't massively oversized
            assert 300 <= chunk_length <= 1600

    def test_chunk_text_sequential_indexing(self):
        """Test chunks are indexed sequentially."""
        # ARRANGE
        text = self.TEST_TEXT * 5

        # ACT
        chunks = ChunkingService.chunk_text(
            text=text, document_id="test-id", page_number=1
        )

        # ASSERT
        for idx, chunk in enumerate(chunks):
            assert chunk["chunk_index"] == idx

    def test_chunk_text_preserves_chapter_metadata(self):
        """Test chapter name is preserved in chunks."""
        # ARRANGE
        text = self.TEST_TEXT
        chapter_name = "Chapter 1: Introduction"

        # ACT
        chunks = ChunkingService.chunk_text(
            text=text, document_id="test-id", page_number=1, chapter_name=chapter_name
        )

        # ASSERT
        assert len(chunks) > 0
        assert chunks[0]["chapter_name"] == chapter_name

    def test_chunk_text_preserves_page_number(self):
        """Test page number is preserved in chunks."""
        # ARRANGE
        text = self.TEST_TEXT
        page_number = 42

        # ACT
        chunks = ChunkingService.chunk_text(
            text=text, document_id="test-id", page_number=page_number
        )

        # ASSERT
        assert len(chunks) > 0
        assert chunks[0]["page_number"] == page_number

    def test_chunk_text_returns_empty_for_empty_input(self):
        """Test empty text returns empty list."""
        # ARRANGE
        text = ""

        # ACT
        chunks = ChunkingService.chunk_text(
            text=text, document_id="test-id", page_number=1
        )

        # ASSERT
        assert chunks == []

    def test_clean_text_removes_extra_whitespace(self):
        """Test text cleaning removes extra spaces."""
        # ARRANGE
        text = "This  has   multiple    spaces."

        # ACT
        cleaned = ChunkingService._clean_text(text)

        # ASSERT
        assert "  " not in cleaned
        assert cleaned == "This has multiple spaces."

    def test_clean_text_normalizes_line_breaks(self):
        """Test multiple line breaks are normalized."""
        # ARRANGE
        text = "Line 1\n\n\nLine 2"

        # ACT
        cleaned = ChunkingService._clean_text(text)

        # ASSERT
        assert "\n\n\n" not in cleaned

    def test_detect_chapter_finds_chapter_pattern(self):
        """Test chapter detection from text."""
        # ARRANGE
        text = "Chapter 5: Democracy and Rights. Content follows..."

        # ACT
        chapter = ChunkingService._detect_chapter(text)

        # ASSERT
        assert "Chapter 5" in chapter

    def test_detect_chapter_returns_unknown_when_not_found(self):
        """Test returns 'Unknown Chapter' when no pattern found."""
        # ARRANGE
        text = "Some random content without chapter marker."

        # ACT
        chapter = ChunkingService._detect_chapter(text)

        # ASSERT
        assert chapter == "Unknown Chapter"

    def test_assess_quality_returns_high_for_good_chunk(self):
        """Test quality assessment returns 'high' for good text."""
        # ARRANGE
        # Use valid length text
        text = self.TEST_TEXT

        # ACT
        quality = ChunkingService._assess_quality(text)

        # ASSERT
        assert quality == "high"

    def test_assess_quality_returns_low_for_short_chunk(self):
        """Test quality assessment returns 'low' for too-short text."""
        # ARRANGE
        text = "Short."

        # ACT
        quality = ChunkingService._assess_quality(text)

        # ASSERT
        assert quality == "low"

    def test_assess_quality_returns_needs_review_for_many_special_chars(self):
        """Test quality returns 'needs_review' for OCR-like errors."""
        # ARRANGE
        # Make a long string (so it passes length check 300+) but with HIGH density of special chars (>10%)
        # Each repeat is 35 chars, 27 of which are special. ~77% ratio.
        text = "@@@ ### $$$ %%% ^^^ &&& *** ((( ))) " * 20

        # ACT
        quality = ChunkingService._assess_quality(text)

        # ASSERT
        assert quality == "needs_review"


# ============================================================================
# EMBEDDING SERVICE TESTS
# ============================================================================


class TestEmbeddingService:
    """Test suite for EmbeddingService."""

    # Patch the library directly everywhere it is used
    @patch("sentence_transformers.SentenceTransformer")
    def test_generate_embedding_returns_384_dim_vector(self, mock_class):
        """Test embedding generation returns 384-dimensional vector."""
        # ARRANGE
        mock_model = Mock()
        mock_model.encode.return_value = Mock(tolist=lambda: [0.1] * 384)
        mock_class.return_value = mock_model

        # Force reload or manually set model to ensure mock is used
        EmbeddingService._model = None

        text = "Test sentence for embedding."

        # ACT
        embedding = EmbeddingService.generate_embedding(text)

        # ASSERT
        assert len(embedding) == 384
        assert all(isinstance(x, float) for x in embedding)

    @patch("sentence_transformers.SentenceTransformer")
    def test_generate_embedding_calls_model_encode(self, mock_class):
        """Test embedding service calls model.encode()."""
        # ARRANGE
        mock_model = Mock()
        mock_model.encode.return_value = Mock(tolist=lambda: [0.1] * 384)
        mock_class.return_value = mock_model

        # Reset singleton
        EmbeddingService._model = None

        text = "Test text"

        # ACT
        EmbeddingService.generate_embedding(text)

        # ASSERT
        mock_model.encode.assert_called_once()

    def test_generate_embedding_handles_empty_text(self):
        """Test empty text returns zero vector."""
        # ARRANGE
        text = ""

        # ACT
        embedding = EmbeddingService.generate_embedding(text)

        # ASSERT
        assert len(embedding) == 384
        assert all(x == 0.0 for x in embedding)

    @patch("sentence_transformers.SentenceTransformer")
    def test_generate_embeddings_batch_processes_multiple_texts(self, mock_class):
        """Test batch embedding generation."""
        # ARRANGE
        mock_model = Mock()
        # Side effect to handle batch encoding
        mock_model.encode.return_value = [
            Mock(tolist=lambda: [0.1] * 384),
            Mock(tolist=lambda: [0.2] * 384),
        ]
        mock_class.return_value = mock_model

        EmbeddingService._model = None

        texts = ["Text 1", "Text 2"]

        # ACT
        embeddings = EmbeddingService.generate_embeddings_batch(texts)

        # ASSERT
        assert len(embeddings) == 2
        assert all(len(emb) == 384 for emb in embeddings)

    def test_generate_embeddings_batch_handles_empty_list(self):
        """Test batch generation with empty input."""
        # ARRANGE
        texts = []

        # ACT
        embeddings = EmbeddingService.generate_embeddings_batch(texts)

        # ASSERT
        assert embeddings == []

    @patch("sentence_transformers.SentenceTransformer")
    def test_create_embedding_record_returns_proper_structure(self, mock_class):
        """Test embedding record has correct structure."""
        # ARRANGE
        mock_model = Mock()
        mock_model.encode.return_value = Mock(tolist=lambda: [0.1] * 384)
        mock_class.return_value = mock_model

        EmbeddingService._model = None

        # ACT
        record = EmbeddingService.create_embedding_record(
            content_type="chunk", content_id="test-chunk-id", text="Test text"
        )

        # ASSERT
        assert record["content_type"] == "chunk"
        assert record["content_id"] == "test-chunk-id"
        assert len(record["vector"]) == 384
        assert record["model_name"] == "all-MiniLM-L6-v2"


# ============================================================================
# INGESTION SERVICE TESTS
# ============================================================================


@pytest.mark.django_db
class TestIngestionService:
    """Test suite for IngestionService."""

    # Use the same long text for mocking
    TEST_TEXT = TestChunkingService.TEST_TEXT

    @patch(
        "engines.content.services.ingestion_service.IngestionService._generate_embeddings_for_chunks"
    )
    @patch("engines.content.services.ingestion_service.ChunkingService.chunk_text")
    @patch(
        "engines.content.services.ingestion_service.IngestionService._extract_text_by_pages"
    )
    @patch("engines.content.services.ingestion_service.IngestionService._save_file")
    def test_ingest_document_creates_document_record(
        self, mock_save_file, mock_extract, mock_chunking, mock_gen_embeddings
    ):
        """Test ingestion creates Document in database."""
        # ARRANGE
        mock_save_file.return_value = "/media/test.txt"
        mock_extract.return_value = [
            {"page_number": 1, "text": self.TEST_TEXT, "chapter": "Chapter 1"}
        ]

        def chunking_side_effect(text, document_id, page_number, chapter_name=None):
            return [
                {
                    "chunk_text": self.TEST_TEXT,
                    "chunk_index": 0,
                    "page_number": page_number,
                    "chapter_name": chapter_name or "Chapter 1",
                    "source_type": "static",
                    "document_id": document_id,
                    "quality_flag": "high",
                    "confidence_score": 1.0,
                }
            ]

        mock_chunking.side_effect = chunking_side_effect
        mock_gen_embeddings.return_value = None

        file = SimpleUploadedFile("test.txt", b"Test content")

        # ACT
        result = IngestionService.ingest_document(
            file=file, title="Test Document", source_type="static"
        )

        # ASSERT
        assert "document_id" in result
        assert Document.objects.filter(title="Test Document").exists()

    @patch(
        "engines.content.services.ingestion_service.IngestionService._generate_embeddings_for_chunks"
    )
    @patch("engines.content.services.ingestion_service.ChunkingService.chunk_text")
    @patch(
        "engines.content.services.ingestion_service.IngestionService._extract_text_by_pages"
    )
    @patch("engines.content.services.ingestion_service.IngestionService._save_file")
    def test_ingest_document_creates_chunks(
        self, mock_save_file, mock_extract, mock_chunking, mock_gen_embeddings
    ):
        """Test ingestion creates Chunk records."""
        # ARRANGE
        mock_save_file.return_value = "/media/test.txt"
        mock_extract.return_value = [
            {"page_number": 1, "text": self.TEST_TEXT, "chapter": "Chapter 1"}
        ]

        def chunking_side_effect(text, document_id, page_number, chapter_name=None):
            return [
                {
                    "chunk_text": self.TEST_TEXT,
                    "chunk_index": 0,
                    "page_number": page_number,
                    "chapter_name": chapter_name or "Chapter 1",
                    "source_type": "static",
                    "document_id": document_id,
                    "quality_flag": "high",
                    "confidence_score": 1.0,
                },
                {
                    "chunk_text": self.TEST_TEXT,
                    "chunk_index": 1,
                    "page_number": page_number,
                    "chapter_name": chapter_name or "Chapter 1",
                    "source_type": "static",
                    "document_id": document_id,
                    "quality_flag": "high",
                    "confidence_score": 1.0,
                },
            ]

        mock_chunking.side_effect = chunking_side_effect
        mock_gen_embeddings.return_value = None

        file = SimpleUploadedFile("test.txt", b"Test content")

        # ACT
        result = IngestionService.ingest_document(
            file=file, title="Test Document", source_type="static"
        )

        # ASSERT
        assert result["chunks_created"] == 2
        assert Chunk.objects.count() == 2

    @patch(
        "engines.content.services.ingestion_service.IngestionService._generate_embeddings_for_chunks"
    )
    @patch("engines.content.services.ingestion_service.ChunkingService.chunk_text")
    @patch(
        "engines.content.services.ingestion_service.IngestionService._extract_text_by_pages"
    )
    @patch("engines.content.services.ingestion_service.IngestionService._save_file")
    def test_ingest_document_creates_embeddings(
        self, mock_save_file, mock_extract, mock_chunking, mock_gen_embeddings
    ):
        """Test ingestion creates Embedding records."""
        # ARRANGE
        mock_save_file.return_value = "/media/test.txt"
        mock_extract.return_value = [
            {"page_number": 1, "text": self.TEST_TEXT, "chapter": "Chapter 1"}
        ]

        def chunking_side_effect(text, document_id, page_number, chapter_name=None):
            return [
                {
                    "chunk_text": self.TEST_TEXT,
                    "chunk_index": 0,
                    "page_number": page_number,
                    "chapter_name": chapter_name or "Chapter 1",
                    "source_type": "static",
                    "document_id": document_id,
                    "quality_flag": "high",
                    "confidence_score": 1.0,
                }
            ]

        mock_chunking.side_effect = chunking_side_effect
        mock_gen_embeddings.return_value = None

        file = SimpleUploadedFile("test.txt", b"Test content")

        # ACT
        IngestionService.ingest_document(
            file=file, title="Test Document", source_type="static"
        )

        # ASSERT
        # Embeddings are now generated by _generate_embeddings_for_chunks (mocked)
        mock_gen_embeddings.assert_called_once()

    @patch(
        "engines.content.services.ingestion_service.IngestionService._generate_embeddings_for_chunks"
    )
    @patch("engines.content.services.ingestion_service.ChunkingService.chunk_text")
    @patch(
        "engines.content.services.ingestion_service.IngestionService._extract_text_by_pages"
    )
    @patch("engines.content.services.ingestion_service.IngestionService._save_file")
    def test_ingest_document_creates_ingestion_job(
        self, mock_save_file, mock_extract, mock_chunking, mock_gen_embeddings
    ):
        """Test ingestion creates IngestionJob record."""
        # ARRANGE
        mock_save_file.return_value = "/media/test.txt"
        mock_extract.return_value = [
            {"page_number": 1, "text": self.TEST_TEXT, "chapter": "Chapter 1"}
        ]

        def chunking_side_effect(text, document_id, page_number, chapter_name=None):
            return [
                {
                    "chunk_text": self.TEST_TEXT,
                    "chunk_index": 0,
                    "page_number": page_number,
                    "chapter_name": chapter_name or "Chapter 1",
                    "source_type": "static",
                    "document_id": document_id,
                    "quality_flag": "high",
                    "confidence_score": 1.0,
                }
            ]

        mock_chunking.side_effect = chunking_side_effect
        mock_gen_embeddings.return_value = None

        file = SimpleUploadedFile("test.txt", b"Test content")

        # ACT
        result = IngestionService.ingest_document(
            file=file, title="Test Document", source_type="static"
        )

        # ASSERT
        assert "job_id" in result
        job = IngestionJob.objects.get(id=result["job_id"])
        assert job.status == "completed"

    @patch(
        "engines.content.services.ingestion_service.IngestionService._extract_text_by_pages"
    )
    @patch("engines.content.services.ingestion_service.IngestionService._save_file")
    @patch("engines.content.services.ingestion_service.ChunkingService.chunk_text")
    def test_ingest_document_handles_failure_gracefully(
        self, mock_chunking, mock_save_file, mock_extract
    ):
        """Test ingestion marks job as failed on exception."""
        # ARRANGE
        mock_save_file.return_value = "/media/test.txt"
        mock_extract.return_value = [
            {"page_number": 1, "text": "Test text", "chapter": "Chapter 1"}
        ]
        mock_chunking.side_effect = Exception("Chunking failed")
        file = SimpleUploadedFile("test.txt", b"Test content")

        # ACT & ASSERT
        with pytest.raises(Exception):
            IngestionService.ingest_document(
                file=file, title="Test Document", source_type="static"
            )

        # Check job marked as failed
        job = IngestionJob.objects.first()
        assert job.status == "failed"
        assert "Chunking failed" in job.error_log

    def test_extract_text_from_text_file(self):
        """Test text extraction from simple text file."""
        # ARRANGE
        file = SimpleUploadedFile("test.txt", b"Test file content")

        # ACT
        text = IngestionService._extract_text(file)

        # ASSERT
        assert text == "Test file content"

    def test_extract_text_handles_unicode(self):
        """Test text extraction handles unicode."""
        # ARRANGE
        file = SimpleUploadedFile("test.txt", "Test unicode: é à ñ".encode("utf-8"))

        # ACT
        text = IngestionService._extract_text(file)

        # ASSERT
        assert "é" in text
        assert "à" in text
        assert "ñ" in text
