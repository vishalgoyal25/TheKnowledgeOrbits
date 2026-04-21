"""Knowledge Engine - View Tests"""

from rest_framework import status
from rest_framework.test import APIClient

import pytest

from engines.auth.models import User
from engines.knowledge.models import Module, Program, Subject, Topic


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


@pytest.mark.django_db
class TestProgramViewSet:
    def test_list_programs(self, api_client):
        Program.objects.create(name="UPSC CSE")
        Program.objects.create(name="State PSC")

        response = api_client.get("/api/v1/knowledge/programs/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2


@pytest.mark.django_db
class TestTopicViewSet:
    def test_list_topics(self, api_client):
        program = Program.objects.create(name="UPSC CSE")
        subject = Subject.objects.create(name="Polity", program=program)
        module = Module.objects.create(name="Constitution", subject=subject)

        Topic.objects.create(name="Article 370", module=module, subject=subject)
        Topic.objects.create(name="Article 371", module=module, subject=subject)

        response = api_client.get("/api/v1/knowledge/topics/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2

    def test_filter_topics_by_difficulty(self, api_client):
        program = Program.objects.create(name="UPSC CSE")
        subject = Subject.objects.create(name="Polity", program=program)
        module = Module.objects.create(name="Constitution", subject=subject)

        Topic.objects.create(
            name="Easy Topic", module=module, subject=subject, difficulty_level="easy"
        )
        Topic.objects.create(
            name="Hard Topic", module=module, subject=subject, difficulty_level="hard"
        )

        response = api_client.get("/api/v1/knowledge/topics/?difficulty=easy")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1


@pytest.mark.django_db
class TestSearchViewSet:
    """Tests for SearchViewSet — limit defaults and cap."""

    def test_search_empty_query_returns_empty_list(self, api_client):
        """Empty or single-char query must return an empty list, not an error."""
        response = api_client.get("/api/v1/knowledge/search/?q=a")
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_search_missing_query_returns_empty_list(self, api_client):
        """Missing ?q param returns []."""
        response = api_client.get("/api/v1/knowledge/search/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_search_limit_cap_at_100(self, api_client):
        """limit=200 must be silently capped to 100 (no error returned)."""
        from unittest.mock import patch

        with patch(
            "engines.knowledge.views.SearchService.semantic_search",
            return_value=[],
        ) as mock_search:
            response = api_client.get("/api/v1/knowledge/search/?q=polity&limit=200")

        assert response.status_code == status.HTTP_200_OK
        # The service must have been called with limit=100, not 200
        called_limit = mock_search.call_args.kwargs.get(
            "limit",
            mock_search.call_args.args[1]
            if len(mock_search.call_args.args) > 1
            else None,
        )
        assert called_limit == 100

    def test_search_default_limit_is_50(self, api_client):
        """When no limit param is provided, service is called with limit=50."""
        from unittest.mock import patch

        with patch(
            "engines.knowledge.views.SearchService.semantic_search",
            return_value=[],
        ) as mock_search:
            response = api_client.get("/api/v1/knowledge/search/?q=economy")

        assert response.status_code == status.HTTP_200_OK
        called_limit = mock_search.call_args.kwargs.get(
            "limit",
            mock_search.call_args.args[1]
            if len(mock_search.call_args.args) > 1
            else None,
        )
        assert called_limit == 50
