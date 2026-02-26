"""User State Engine Integration Tests."""

import uuid

from rest_framework import status
from rest_framework.test import APIClient

import pytest

from engines.auth.models import User


@pytest.fixture
def api_client():
    """Return API client."""
    return APIClient()


@pytest.fixture
def authenticated_user_client(api_client):
    """Return an authenticated user and client."""
    user = User.objects.create_user(email="test@example.com", password="pass")
    user.is_verified = True
    user.save()
    api_client.force_authenticate(user=user)
    return api_client, user


@pytest.mark.django_db
class TestBookmarkFlow:
    """Test complete bookmark workflow."""

    def test_add_view_remove_bookmark_flow(self, authenticated_user_client):
        """Test: Add → View → Remove bookmark."""
        client, user = authenticated_user_client

        # Step 1: Add bookmark
        content_id = str(uuid.uuid4())
        response = client.post(
            "/api/v1/userstate/bookmarks/add/",
            {
                "content_type": "article",
                "content_id": content_id,
                "notes": "Important article",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        bookmark_id = response.data["id"]

        # Step 2: View bookmarks
        response = client.get("/api/v1/userstate/bookmarks/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

        # Step 3: Remove bookmark
        response = client.delete(f"/api/v1/userstate/bookmarks/{bookmark_id}/")
        assert response.status_code == status.HTTP_200_OK

        # Step 4: Verify removed
        response = client.get("/api/v1/userstate/bookmarks/")
        assert len(response.data["results"]) == 0


@pytest.mark.django_db
class TestProgressTracking:
    """Test progress tracking workflow."""

    def test_activity_updates_progress(self, authenticated_user_client):
        """Test that activities update progress stats."""
        client, user = authenticated_user_client
        from engines.userstate.services.activity_service import ActivityService

        # Create activities
        service = ActivityService()
        service.log_article_read(user, str(uuid.uuid4()))
        service.log_quiz_completed(user, str(uuid.uuid4()), str(uuid.uuid4()), 80.0)

        # Get progress
        response = client.get("/api/v1/userstate/progress/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["total_articles_read"] == 1
        assert response.data["total_quizzes_taken"] == 1


@pytest.mark.django_db
class TestMasteryTracking:
    """Test mastery tracking workflow."""

    def test_quiz_updates_mastery(self, authenticated_user_client):
        """Test quiz completion updates topic mastery."""
        client, user = authenticated_user_client
        from engines.knowledge.models import Module, Program, Subject, Topic
        from engines.userstate.services.mastery_service import MasteryService

        # Create topic with full hierarchy
        program = Program.objects.create(name="Test Program")
        subject = Subject.objects.create(name="Test Subject", program=program)
        module = Module.objects.create(name="Test Module", subject=subject)
        topic = Topic.objects.create(name="Test Topic", module=module, subject=subject)

        # Simulate quiz questions
        service = MasteryService()
        service.update_mastery(user, str(topic.id), is_correct=True)
        service.update_mastery(user, str(topic.id), is_correct=True)
        service.update_mastery(user, str(topic.id), is_correct=False)

        # Check mastery
        response = client.get("/api/v1/userstate/mastery/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["mastery_score"] == pytest.approx(66.67, 0.1)
