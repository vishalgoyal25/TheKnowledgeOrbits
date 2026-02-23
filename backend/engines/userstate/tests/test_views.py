"""User State Engine View Tests."""

import uuid

from rest_framework import status
from rest_framework.test import APIClient

import pytest

from engines.auth.models import User
from engines.userstate.models import Bookmark, UserEvent


@pytest.fixture
def api_client():
    """Return API client fixture."""
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
    """Return an authenticated API client."""
    api_client.force_authenticate(user=user)
    return api_client, user


@pytest.mark.django_db
class TestGetProgressView:
    """Test get progress endpoint."""

    def test_get_progress_success(self, authenticated_client):
        """Test getting user progress."""
        client, user = authenticated_client

        # Create some events
        UserEvent.objects.create(
            user=user,
            event_type="article_read",
            event_data={"article_id": str(uuid.uuid4())},
        )
        UserEvent.objects.create(
            user=user,
            event_type="quiz_completed",
            event_data={"quiz_id": str(uuid.uuid4())},
        )

        response = client.get("/api/v1/userstate/progress/")

        assert response.status_code == status.HTTP_200_OK
        assert "total_articles_read" in response.data
        assert "current_streak" in response.data

    def test_get_progress_unauthenticated(self, api_client):
        """Test get progress fails without auth."""
        response = api_client.get("/api/v1/userstate/progress/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestGetMasteryView:
    """Test get mastery endpoint."""

    def test_get_mastery_all(self, authenticated_client):
        """Test getting all masteries."""
        client, user = authenticated_client

        response = client.get("/api/v1/userstate/mastery/")

        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)

    def test_get_mastery_weak_filter(self, authenticated_client):
        """Test filtering weak topics."""
        client, user = authenticated_client

        response = client.get("/api/v1/userstate/mastery/?weak=true")

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestGetEventsView:
    """Test get events endpoint."""

    def test_get_events_success(self, authenticated_client):
        """Test getting recent events."""
        client, user = authenticated_client

        # Create events
        UserEvent.objects.create(user=user, event_type="login")
        UserEvent.objects.create(user=user, event_type="article_read")

        response = client.get("/api/v1/userstate/events/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_get_events_with_limit(self, authenticated_client):
        """Test events with limit parameter."""
        client, user = authenticated_client

        # Create 5 events
        for _ in range(5):
            UserEvent.objects.create(user=user, event_type="login")

        response = client.get("/api/v1/userstate/events/?limit=3")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 3


@pytest.mark.django_db
class TestBookmarkViews:
    """Test bookmark endpoints."""

    def test_add_bookmark_success(self, authenticated_client):
        """Test adding bookmark."""
        client, user = authenticated_client

        data = {
            "content_type": "article",
            "content_id": str(uuid.uuid4()),
            "notes": "Test bookmark",
        }

        response = client.post("/api/v1/userstate/bookmarks/add/", data)

        assert response.status_code == status.HTTP_201_CREATED
        assert Bookmark.objects.filter(user=user).count() == 1

    def test_add_duplicate_bookmark_fails(self, authenticated_client):
        """Test adding duplicate bookmark fails."""
        client, user = authenticated_client

        content_id = str(uuid.uuid4())
        data = {"content_type": "article", "content_id": content_id}

        # First bookmark
        client.post("/api/v1/userstate/bookmarks/add/", data)

        # Duplicate
        response = client.post("/api/v1/userstate/bookmarks/add/", data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_bookmarks(self, authenticated_client):
        """Test listing bookmarks."""
        client, user = authenticated_client

        # Create bookmarks
        Bookmark.objects.create(
            user=user, content_type="article", content_id=uuid.uuid4()
        )
        Bookmark.objects.create(user=user, content_type="quiz", content_id=uuid.uuid4())

        response = client.get("/api/v1/userstate/bookmarks/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_remove_bookmark(self, authenticated_client):
        """Test removing bookmark."""
        client, user = authenticated_client

        bookmark = Bookmark.objects.create(
            user=user, content_type="article", content_id=uuid.uuid4()
        )

        response = client.delete(f"/api/v1/userstate/bookmarks/{bookmark.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert Bookmark.objects.filter(id=bookmark.id).count() == 0


@pytest.mark.django_db
class TestReadingProgressViews:
    """Test reading progress endpoints."""

    def test_get_reading_progress_exists(self, authenticated_client):
        """Test getting existing reading progress."""
        client, user = authenticated_client
        from engines.userstate.models import ReadingProgress

        article_id = uuid.uuid4()
        ReadingProgress.objects.create(
            user=user, article_id=article_id, percent_read=50.0, last_position=1000
        )

        response = client.get(f"/api/v1/userstate/reading-progress/{article_id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["percent_read"] == 50.0

    def test_get_reading_progress_not_exists(self, authenticated_client):
        """Test getting non-existent progress returns defaults."""
        client, user = authenticated_client

        article_id = uuid.uuid4()
        response = client.get(f"/api/v1/userstate/reading-progress/{article_id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["percent_read"] == 0

    def test_update_reading_progress(self, authenticated_client):
        """Test updating reading progress."""
        client, user = authenticated_client

        article_id = uuid.uuid4()
        data = {"percent_read": 75.5, "last_position": 2500}

        response = client.put(
            f"/api/v1/userstate/reading-progress/{article_id}/update/",
            data,
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["percent_read"] == 75.5
