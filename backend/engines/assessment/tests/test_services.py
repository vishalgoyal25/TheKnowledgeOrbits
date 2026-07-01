"""
Assessment Engine - Service Tests

Tests for QuizGeneratorService (mocked GROQ).
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from engines.assessment.services.quiz_generator import QuizGeneratorService
from engines.content.models import Chunk, Document
from engines.knowledge.models import ChunkTopicMap, Module, Program, Subject, Topic


@pytest.fixture
def topic():
    """Create test topic with full hierarchy."""
    program = Program.objects.create(name="UPSC CSE")
    subject = Subject.objects.create(name="Test", program=program)
    module = Module.objects.create(name="Test Module", subject=subject)
    return Topic.objects.create(
        name="Test Topic",
        module=module,
        subject=subject,
        description="A test topic for quiz generation",
    )


@pytest.fixture
def chunks(topic):
    """Create test chunks mapped to topic via ChunkTopicMap."""
    document = Document.objects.create(
        title="Test Doc", source_type="static", file_path="/test.pdf"
    )

    chunks = []
    for i in range(5):
        chunk = Chunk.objects.create(
            document=document,
            chunk_index=i,
            chunk_text=f"Test content about topic {i}. "
            f"This is comprehensive educational material for UPSC preparation. " * 5,
            source_type="static",
        )
        # Map chunk to topic
        ChunkTopicMap.objects.create(chunk=chunk, topic=topic, relevance_score=0.9)
        chunks.append(chunk)

    return chunks


@pytest.mark.django_db
class TestQuizGeneratorService:
    """Test QuizGeneratorService."""

    def test_generate_quiz_basic(self, topic, chunks):
        """Test basic quiz generation."""
        mock_message = MagicMock()
        mock_message.content = '{"questions": [{"question_text": "Test question?", "options": {"A": "Option 1", "B": "Option 2", "C": "Option 3", "D": "Option 4"}, "correct_answer": "A", "explanation": "Test explanation", "question_type": "single_mcq", "difficulty": "medium"}]}'
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_entry = MagicMock()
        mock_entry.client = mock_client
        mock_entry.model = "openai/gpt-oss-120b"
        mock_entry.provider = "groq"

        with (
            patch("engines.book_content.services.llm_service._pool", [mock_entry]),
            patch("engines.book_content.services.llm_service._pool_size", 1),
        ):
            service = QuizGeneratorService()
            quiz = service.generate_quiz(
                topic_id=str(topic.id),
                difficulty="medium",
                include_ca=False,
                question_count=5,
            )

            assert quiz is not None
            assert quiz.topic == topic
            assert quiz.difficulty_level == "medium"

    def test_generate_quiz_invalid_topic(self):
        """Test generation fails with invalid topic."""
        service = QuizGeneratorService()

        with pytest.raises(ValueError, match="not found"):
            service.generate_quiz(
                topic_id=str(uuid.uuid4()),
                difficulty="medium",
                include_ca=False,
                question_count=5,
            )
