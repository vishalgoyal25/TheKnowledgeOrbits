"""Knowledge Engine - Integration Tests"""

from rest_framework.test import APIClient

import pytest

from engines.auth.models import User
from engines.content.models import Chunk, Document
from engines.knowledge.models import ChunkTopicMap, Module, Program, Subject, Topic


@pytest.fixture
def authenticated_user():
    user = User.objects.create_user(email="test@test.com", password="pass")
    user.is_verified = True
    user.save()

    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.mark.django_db
class TestKnowledgeHierarchyFlow:
    def test_complete_hierarchy_flow(self, authenticated_user):
        """Test: Program → Subject → Module → Topic → Chunks"""
        client, user = authenticated_user

        # Create hierarchy
        program = Program.objects.create(name="UPSC CSE")
        subject = Subject.objects.create(name="Polity", program=program)
        module = Module.objects.create(name="Constitution", subject=subject)
        topic = Topic.objects.create(name="Article 370", module=module, subject=subject)

        # Create chunks
        doc = Document.objects.create(
            title="Constitution PDF", file_path="/const.pdf", source_type="static"
        )
        chunk = Chunk.objects.create(
            chunk_text="Article 370 content",
            chunk_index=0,
            source_type="static",
            document=doc,
        )

        # Map chunk to topic
        ChunkTopicMap.objects.create(chunk=chunk, topic=topic, relevance_score=0.9)

        # Verify via API
        response = client.get(f"/api/v1/knowledge/topics/{topic.id}/chunks/")

        assert response.status_code == 200
        assert len(response.data) == 1
