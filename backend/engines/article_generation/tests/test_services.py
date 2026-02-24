"""
Article Generation Engine - Service Tests

Tests for ArticleGenerationService (mocked GROQ calls).
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from engines.article_generation.services.generation_service import (
    ArticleGenerationService,
)
from engines.content.models import Chunk, Document
from engines.knowledge.models import Module, Program, Subject, Topic


@pytest.fixture
def topic():
    """Create test topic with full hierarchy."""
    program = Program.objects.create(name="UPSC CSE")
    subject = Subject.objects.create(name="Polity", program=program)
    module = Module.objects.create(name="Constitution", subject=subject)
    return Topic.objects.create(
        name="Article 370",
        module=module,
        subject=subject,
        description="Special status of Jammu and Kashmir",
    )


@pytest.fixture
def chunks(topic):
    """Create test chunks mapped to topic via ChunkTopicMap."""
    from engines.knowledge.models import ChunkTopicMap

    document = Document.objects.create(
        title="Test Doc", source_type="static", file_path="/test.pdf"
    )

    chunks = []
    for i in range(3):
        chunk = Chunk.objects.create(
            document=document,
            chunk_index=i,
            chunk_text=f"Chunk content about Article 370 paragraph {i}. "
            f"This is a comprehensive analysis of the constitutional provisions. " * 10,
            source_type="static",
        )
        # Map chunk to topic
        ChunkTopicMap.objects.create(chunk=chunk, topic=topic, relevance_score=0.9)
        chunks.append(chunk)

    return chunks


@pytest.mark.django_db
class TestArticleGenerationService:
    """Test ArticleGenerationService."""

    @patch(
        "engines.content.services.embedding_service.EmbeddingService.generate_embedding"
    )
    @patch("engines.article_generation.services.generation_service.Groq")
    def test_generate_article_basic(
        self, mock_groq_class, mock_embedding, topic, chunks
    ):
        """Test basic article generation."""
        # Mock GROQ client instance
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client

        # Generate enough content to pass quality checks
        generated_content = (
            "# Generated Article About Article 370\n\n"
            "This is a comprehensive overview of Article 370. " * 50 + "\n\n"
            "The constitutional framework provides special status. " * 30 + "\n\n"
            "In conclusion, understanding Article 370 is essential for UPSC preparation. "
            * 20
        )

        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=generated_content))]
        )

        result = ArticleGenerationService.generate_article(
            topic_id=str(topic.id), include_ca=False, user_id=None
        )

        assert "article_id" in result
        assert result["word_count"] > 0
        assert result["quality_score"] >= 0

    def test_generate_article_invalid_topic(self):
        """Test generation fails with invalid topic."""
        with pytest.raises(Topic.DoesNotExist):
            ArticleGenerationService.generate_article(
                topic_id=str(uuid.uuid4()), include_ca=False, user_id=None
            )
