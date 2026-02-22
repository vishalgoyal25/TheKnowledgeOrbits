"""
User State Engine - Service Tests

Tests for ActivityService, BookmarkService, MasteryService, ProgressService.
"""

import pytest
import uuid
from engines.auth.models import User
from engines.userstate.models import UserEvent, Bookmark, TopicMastery
from engines.userstate.services.activity_service import ActivityService
from engines.userstate.services.bookmark_service import BookmarkService
from engines.userstate.services.mastery_service import MasteryService
from engines.userstate.services.progress_service import ProgressService


@pytest.fixture
def user():
    """Create test user."""
    return User.objects.create_user(email="test@example.com", password="pass")


@pytest.fixture
def topic():
    """Create test topic with full hierarchy."""
    from engines.knowledge.models import Program, Subject, Module, Topic

    program = Program.objects.create(name="Test Program")
    subject = Subject.objects.create(name="Test Subject", program=program)
    module = Module.objects.create(name="Test Module", subject=subject)
    return Topic.objects.create(name="Test Topic", module=module, subject=subject)


@pytest.mark.django_db
class TestActivityService:
    """Test ActivityService."""

    def test_log_event(self, user):
        """Test logging generic event."""
        service = ActivityService()

        event = service.log_event(
            user=user, event_type="login", event_data={"ip": "127.0.0.1"}
        )

        assert event.user == user
        assert event.event_type == "login"
        assert event.event_data["ip"] == "127.0.0.1"

    def test_log_article_read(self, user):
        """Test logging article read event."""
        service = ActivityService()
        article_id = str(uuid.uuid4())

        event = service.log_article_read(user, article_id)

        assert event.event_type == "article_read"
        assert event.event_data["article_id"] == article_id

    def test_log_quiz_completed(self, user):
        """Test logging quiz completion."""
        service = ActivityService()

        event = service.log_quiz_completed(
            user, str(uuid.uuid4()), str(uuid.uuid4()), 85.0
        )

        assert event.event_type == "quiz_completed"
        assert event.event_data["score"] == 85.0


@pytest.mark.django_db
class TestBookmarkService:
    """Test BookmarkService."""

    def test_add_bookmark(self, user):
        """Test adding bookmark."""
        service = BookmarkService()

        bookmark = service.add_bookmark(
            user=user, content_type="article", content_id=str(uuid.uuid4())
        )

        assert bookmark.user == user
        assert bookmark.content_type == "article"

    def test_add_duplicate_bookmark_fails(self, user):
        """Test adding duplicate fails."""
        service = BookmarkService()
        content_id = str(uuid.uuid4())

        service.add_bookmark(user, "article", content_id)

        with pytest.raises(ValueError, match="already bookmarked"):
            service.add_bookmark(user, "article", content_id)

    def test_remove_bookmark(self, user):
        """Test removing bookmark."""
        service = BookmarkService()

        bookmark = service.add_bookmark(user, "article", str(uuid.uuid4()))

        result = service.remove_bookmark(user, str(bookmark.id))

        assert result is True
        assert Bookmark.objects.filter(id=bookmark.id).count() == 0

    def test_get_bookmarks(self, user):
        """Test getting all bookmarks."""
        service = BookmarkService()

        service.add_bookmark(user, "article", str(uuid.uuid4()))
        service.add_bookmark(user, "quiz", str(uuid.uuid4()))

        bookmarks = service.get_bookmarks(user)

        assert len(bookmarks) == 2


@pytest.mark.django_db
class TestMasteryService:
    """Test MasteryService."""

    def test_update_mastery_correct_answer(self, user, topic):
        """Test updating mastery with correct answer."""
        service = MasteryService()

        mastery = service.update_mastery(user, str(topic.id), is_correct=True)

        assert mastery.questions_attempted == 1
        assert mastery.questions_correct == 1
        assert mastery.mastery_score == 100.0

    def test_update_mastery_incorrect_answer(self, user, topic):
        """Test updating mastery with incorrect answer."""
        service = MasteryService()

        mastery = service.update_mastery(user, str(topic.id), is_correct=False)

        assert mastery.questions_attempted == 1
        assert mastery.questions_correct == 0
        assert mastery.mastery_score == 0.0

    def test_get_weak_topics(self, user, topic):
        """Test getting weak topics."""
        service = MasteryService()

        # Create weak mastery
        TopicMastery.objects.create(
            user=user,
            topic=topic,
            mastery_score=40.0,
            questions_attempted=5,
            questions_correct=2,
        )

        weak = service.get_weak_topics(user)

        assert weak.count() == 1


@pytest.mark.django_db
class TestProgressService:
    """Test ProgressService."""

    def test_get_or_create_progress(self, user):
        """Test getting or creating progress."""
        service = ProgressService()

        progress = service.get_or_create_progress(user)

        assert progress.user == user
        assert progress.total_articles_read == 0

    def test_update_progress(self, user):
        """Test updating progress from events."""
        service = ProgressService()

        # Create events
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

        progress = service.update_progress(user)

        assert progress.total_articles_read == 1
        assert progress.total_quizzes_taken == 1
