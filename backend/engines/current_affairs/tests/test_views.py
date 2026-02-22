"""
Current Affairs Engine - View Tests

Tests for CA viewsets.
"""

import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from engines.current_affairs.models import CASource, CAArticle, CAChunk
from engines.auth.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    user = User.objects.create_user(email="test@test.com", password="pass")
    user.is_verified = True
    user.save()
    return user


@pytest.fixture
def authenticated_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client, user


@pytest.fixture
def ca_source():
    return CASource.objects.create(
        name="The Hindu", url="https://test.com/rss", is_active=True
    )


@pytest.mark.django_db
class TestCASourceViewSet:
    """Test CA Source viewset."""

    def test_list_sources(self, api_client, ca_source):
        """Test listing CA sources."""
        response = api_client.get("/api/v1/ca/sources/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1


@pytest.mark.django_db
class TestCAArticleViewSet:
    """Test CA Article viewset."""

    def test_list_articles(self, api_client, ca_source):
        """Test listing CA articles."""
        CAArticle.objects.create(
            source=ca_source,
            title="Article 1",
            url="https://test.com/1",
            content="Content",
            published_at=timezone.now(),
        )

        response = api_client.get("/api/v1/ca/articles/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1


@pytest.mark.django_db
class TestCAChunkViewSet:
    """Test CA Chunk viewset."""

    def test_list_chunks(self, api_client, ca_source):
        """Test listing CA chunks."""
        article = CAArticle.objects.create(
            source=ca_source,
            title="Article",
            url="https://test.com/1",
            content="Content",
            published_at=timezone.now(),
        )

        CAChunk.objects.create(
            ca_article=article,
            chunk_text="Chunk content",
            chunk_index=0,
            published_at=timezone.now(),
        )

        response = api_client.get("/api/v1/ca/chunks/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
