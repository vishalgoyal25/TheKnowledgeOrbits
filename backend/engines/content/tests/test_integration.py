"""
Content Engine - Integration Tests

End-to-end content ingestion workflows.
"""

import pytest
from rest_framework.test import APIClient
from rest_framework import status
from engines.content.models import Document, Chunk
from engines.auth.models import User, Role, RoleAssignment


@pytest.fixture
def authenticated_admin():
    """Authenticated admin user."""
    user = User.objects.create_user(email="admin@test.com", password="pass")
    user.is_verified = True
    user.save()
    role, _ = Role.objects.get_or_create(name="admin")
    RoleAssignment.objects.create(user=user, role=role)

    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.mark.django_db
class TestContentIngestionFlow:
    """Test complete content ingestion workflow."""

    def test_document_to_chunks_flow(self, authenticated_admin):
        """Test: Upload Document → Create Chunks → Verify."""
        client, user = authenticated_admin

        # Step 1: Create document
        doc = Document.objects.create(
            title="NCERT Polity", file_path="/ncert.pdf", source_type="static"
        )

        # Step 2: Create chunks
        for i in range(5):
            Chunk.objects.create(
                chunk_text=f"Content chunk {i}",
                chunk_index=i,
                source_type="static",
                document=doc,
                chapter_name="Chapter 1",
            )

        # Step 3: Verify chunks via API
        response = client.get(f"/api/v1/content/documents/{doc.id}/chunks/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 5

        # Step 4: Verify chunks are ordered
        for i, chunk in enumerate(response.data):
            assert chunk["chunk_index"] == i
