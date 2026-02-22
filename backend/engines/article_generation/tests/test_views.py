"""
Article Generation Engine - View Tests

Tests for article viewset endpoints.
"""

import pytest
import uuid
from unittest.mock import patch
from rest_framework.test import APIClient
from rest_framework import status
from engines.article_generation.models import Article
from engines.auth.models import User
from engines.knowledge.models import Program, Subject, Module, Topic


@pytest.fixture
def api_client():
    """API client fixture."""
    return APIClient()


@pytest.fixture
def user():
    """Create test user."""
    user = User.objects.create_user(email="test@example.com", password="pass")
    user.is_verified = True
    user.save()
    return user


@pytest.fixture
def authenticated_client(api_client, user):
    """Authenticated API client."""
    api_client.force_authenticate(user=user)
    return api_client, user


@pytest.fixture
def topic():
    """Create test topic with full hierarchy."""
    program = Program.objects.create(name="UPSC CSE")
    subject = Subject.objects.create(name="Polity", program=program)
    module = Module.objects.create(name="Constitution", subject=subject)
    return Topic.objects.create(name="Test Topic", module=module, subject=subject)


@pytest.mark.django_db
class TestArticleListView:
    """Test article list endpoint."""

    def test_list_articles(self, api_client, topic):
        """Test listing articles."""
        # Create public articles
        Article.objects.create(
            title="Public Article",
            content="Article content here",
            topic=topic,
            is_published=True,
            is_public=True,
        )

        response = api_client.get("/api/v1/articles/")

        assert response.status_code == status.HTTP_200_OK

    def test_list_filters_unpublished(self, api_client, topic):
        """Test unpublished articles not shown."""
        Article.objects.create(
            title="Draft Article",
            content="Draft content",
            topic=topic,
            is_published=False,
        )

        response = api_client.get("/api/v1/articles/")

        assert response.status_code == status.HTTP_200_OK
        # Unpublished should not appear (paginated: results key)
        articles = response.data["results"]
        titles = [a["title"] for a in articles]
        assert "Draft Article" not in titles

    def test_list_private_articles_hidden_from_anonymous(self, api_client, topic, user):
        """Test private articles not visible to anonymous users."""
        Article.objects.create(
            title="Private Article",
            content="Private content",
            topic=topic,
            created_by=user,
            is_public=False,
            is_published=True,
        )

        response = api_client.get("/api/v1/articles/")

        assert response.status_code == status.HTTP_200_OK
        articles = response.data["results"]
        titles = [a["title"] for a in articles]
        assert "Private Article" not in titles

    def test_list_shows_own_private_articles(self, authenticated_client, topic):
        """Test user sees own private articles."""
        client, user = authenticated_client

        Article.objects.create(
            title="My Private Article",
            content="My private content",
            topic=topic,
            created_by=user,
            is_public=False,
            is_published=True,
        )

        response = client.get("/api/v1/articles/")

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestArticleDetailView:
    """Test article detail endpoint."""

    def test_get_article_detail(self, api_client, topic):
        """Test getting article details."""
        article = Article.objects.create(
            title="Test Article",
            content="Full content here",
            topic=topic,
            is_published=True,
            is_public=True,
        )

        response = api_client.get(f"/api/v1/articles/{article.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "Test Article"


@pytest.mark.django_db
class TestArticleGenerateView:
    """Test article generation endpoint."""

    @patch("engines.article_generation.views.ArticleGenerationService.generate_article")
    def test_generate_article_authenticated(
        self, mock_generate, authenticated_client, topic
    ):
        """Test authenticated user generates private article."""
        client, user = authenticated_client

        # Create article that mock will "generate"
        article = Article.objects.create(
            title="Generated Article",
            content="Generated content",
            topic=topic,
            is_published=True,
        )

        mock_generate.return_value = {
            "article_id": str(article.id),
            "word_count": 500,
            "quality_score": 85.0,
            "source_chunks": 5,
        }

        data = {"topic_id": str(topic.id), "include_ca": True}

        response = client.post("/api/v1/articles/generate/", data)

        assert response.status_code == status.HTTP_201_CREATED

        # Check article ownership
        article.refresh_from_db()
        assert article.created_by == user
        assert not article.is_public

    @patch("engines.article_generation.views.ArticleGenerationService.generate_article")
    def test_generate_article_invalid_topic(self, mock_generate, authenticated_client):
        """Test generation fails with invalid topic."""
        client, user = authenticated_client

        mock_generate.side_effect = ValueError("No source material found")

        data = {"topic_id": str(uuid.uuid4()), "include_ca": False}  # Non-existent

        response = client.post("/api/v1/articles/generate/", data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestMyNotebookView:
    """Test my notebook endpoint."""

    def test_my_notebook_returns_private_articles(self, authenticated_client, topic):
        """Test my notebook shows user's private articles."""
        client, user = authenticated_client

        # Create user's private article
        Article.objects.create(
            title="My Article",
            content="My content",
            topic=topic,
            created_by=user,
            is_public=False,
        )

        # Create someone else's article
        other_user = User.objects.create_user(email="other@test.com", password="pass")
        Article.objects.create(
            title="Other Article",
            content="Other content",
            topic=topic,
            created_by=other_user,
            is_public=False,
        )

        response = client.get("/api/v1/articles/my-notebook/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["title"] == "My Article"
