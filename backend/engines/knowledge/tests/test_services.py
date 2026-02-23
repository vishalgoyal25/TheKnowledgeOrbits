"""Knowledge Engine - Service Tests"""

from unittest.mock import patch

import pytest

from engines.content.models import Chunk, Document, Embedding
from engines.knowledge.models import Module, Program, Subject, Topic
from engines.knowledge.services.mapping_service import MappingService


@pytest.fixture
def hierarchy():
    """Create knowledge hierarchy."""
    program = Program.objects.create(name="UPSC CSE")
    subject = Subject.objects.create(name="Polity", program=program)
    module = Module.objects.create(name="Constitution", subject=subject)
    topic = Topic.objects.create(
        name="Article 370",
        module=module,
        subject=subject,
        description="Article 370 special status",
    )
    return topic


@pytest.fixture
def chunks():
    """Create test chunks with embeddings."""
    doc = Document.objects.create(
        title="Test Doc", file_path="/test.pdf", source_type="static"
    )

    chunks_data = []
    for i in range(3):
        chunk = Chunk.objects.create(
            chunk_text=f"Test content {i}",
            chunk_index=i,
            source_type="static",
            document=doc,
        )

        # Create embedding
        Embedding.objects.create(
            content_type="chunk", content_id=chunk.id, vector=[0.1 * i] * 384
        )

        chunks_data.append(chunk)

    return chunks_data


@pytest.mark.django_db
class TestMappingService:
    @patch(
        "engines.content.services.embedding_service.EmbeddingService.generate_embedding"
    )
    def test_auto_suggest_chunks(self, mock_embedding, hierarchy, chunks):
        """Test auto-suggest chunks for topic."""
        mock_embedding.return_value = [0.5] * 384

        suggestions = MappingService.auto_suggest_chunks(
            topic_id=str(hierarchy.id), limit=10
        )

        assert isinstance(suggestions, list)

    def test_cosine_similarity(self):
        """Test cosine similarity calculation."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        similarity = MappingService._cosine_similarity(vec1, vec2)
        assert similarity == 0.0

        vec3 = [1.0, 0.0, 0.0]
        vec4 = [1.0, 0.0, 0.0]

        similarity = MappingService._cosine_similarity(vec3, vec4)
        assert similarity == 1.0
