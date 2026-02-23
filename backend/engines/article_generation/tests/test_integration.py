"""
Article Generation Engine - Integration Tests

End-to-end article generation workflows.
"""

from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APIClient

import pytest

from engines.article_generation.models import Article
from engines.auth.models import User
from engines.knowledge.models import Module, Program, Subject, Topic


@pytest.fixture
def api_client():
    """API client."""
    return APIClient()


@pytest.fixture
def authenticated_user(api_client):
    """Authenticated user and client."""
    user = User.objects.create_user(email="test@example.com", password="pass")
    user.is_verified = True
    user.save()
    api_client.force_authenticate(user=user)
    return api_client, user


@pytest.fixture
def topic():
    """Create topic with full hierarchy."""
    program = Program.objects.create(name="UPSC CSE")
    subject = Subject.objects.create(name="Polity", program=program)
    module = Module.objects.create(name="Constitution", subject=subject)
    return Topic.objects.create(name="Test Topic", module=module, subject=subject)


@pytest.mark.django_db
class TestArticleGenerationFlow:
    """Test complete article generation workflow."""

    @patch("engines.article_generation.views.ArticleGenerationService.generate_article")
    def test_generate_read_flow(self, mock_generate, authenticated_user, topic):
        """Test: Generate → Read article."""
        client, user = authenticated_user

        # Step 1: Pre-create article (simulating what service would do)
        article = Article.objects.create(
            title="Test Article",
            content="Test content about Indian polity",
            topic=topic,
            is_published=True,
        )

        mock_generate.return_value = {
            "article_id": str(article.id),
            "word_count": 500,
            "quality_score": 85.0,
            "source_chunks": 3,
        }

        response = client.post(
            "/api/v1/articles/generate/",
            {"topic_id": str(topic.id), "include_ca": False},
        )

        assert response.status_code == status.HTTP_201_CREATED
        article_id = response.data["article"]["id"]

        # Step 2: Read article
        response = client.get(f"/api/v1/articles/{article_id}/")
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestPrivateArticleWorkflow:
    """Test private article (My Notebook) workflow."""

    @patch("engines.article_generation.views.ArticleGenerationService.generate_article")
    def test_private_article_visibility(self, mock_generate, authenticated_user, topic):
        """Test private articles only visible to owner."""
        client, user = authenticated_user

        # Generate private article
        article = Article.objects.create(
            title="Private Article",
            content="Private content",
            topic=topic,
            is_published=True,
        )

        mock_generate.return_value = {
            "article_id": str(article.id),
            "word_count": 500,
            "quality_score": 85.0,
            "source_chunks": 3,
        }

        response = client.post(
            "/api/v1/articles/generate/",
            {"topic_id": str(topic.id), "include_ca": False},
        )
        assert response.status_code == status.HTTP_201_CREATED

        # Check in My Notebook
        response = client.get("/api/v1/articles/my-notebook/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

        # Check not in public list (when logged out)
        client.logout()
        response = client.get("/api/v1/articles/")
        assert response.status_code == status.HTTP_200_OK
        articles = response.data["results"]
        private_articles = [a for a in articles if a["id"] == str(article.id)]
        assert len(private_articles) == 0
