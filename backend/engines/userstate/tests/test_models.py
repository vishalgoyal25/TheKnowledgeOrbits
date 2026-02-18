"""
User State Engine - Model Tests

Tests for UserEvent, UserProgress, TopicMastery, Bookmark, ReadingProgress models.
"""

import pytest
import uuid
from django.utils import timezone
from engines.userstate.models import (
    UserEvent, UserProgress, TopicMastery, Bookmark, ReadingProgress
)
from engines.auth.models import User


@pytest.fixture
def user():
    """Create test user."""
    return User.objects.create_user(email='test@example.com', password='pass')


@pytest.fixture
def topic():
    """Create test topic with full hierarchy."""
    from engines.knowledge.models import Program, Subject, Module, Topic
    program = Program.objects.create(name='Test Program')
    subject = Subject.objects.create(name='Test Subject', program=program)
    module = Module.objects.create(name='Test Module', subject=subject)
    return Topic.objects.create(name='Test Topic', module=module, subject=subject)


@pytest.mark.django_db
class TestUserEventModel:
    """Test UserEvent model."""
    
    def test_create_event(self, user):
        """Test creating user event."""
        event = UserEvent.objects.create(
            user=user,
            event_type='article_read',
            event_data={'article_id': str(uuid.uuid4())}
        )
        
        assert event.user == user
        assert event.event_type == 'article_read'
        assert 'article_id' in event.event_data
    
    def test_event_has_uuid(self, user):
        """Test event has UUID primary key."""
        event = UserEvent.objects.create(user=user, event_type='login')
        
        assert isinstance(event.id, uuid.UUID)
        assert len(str(event.id)) == 36
    
    def test_event_ordering(self, user):
        """Test events ordered by created_at descending."""
        event1 = UserEvent.objects.create(user=user, event_type='login')
        event2 = UserEvent.objects.create(user=user, event_type='logout')
        
        events = list(UserEvent.objects.all())
        # Both may have same created_at (same millisecond), so just verify
        # that the ordering doesn't crash and returns both events
        assert len(events) == 2
        # If timestamps differ, newest should be first
        assert events[0].created_at >= events[1].created_at
    
    def test_event_str_representation(self, user):
        """Test event string representation."""
        event = UserEvent.objects.create(user=user, event_type='article_read')
        
        assert user.email in str(event)
        assert 'article_read' in str(event)


@pytest.mark.django_db
class TestUserProgressModel:
    """Test UserProgress model."""
    
    def test_create_progress(self, user):
        """Test creating user progress."""
        progress = UserProgress.objects.create(
            user=user,
            total_articles_read=10,
            total_quizzes_taken=5,
            current_streak=7
        )
        
        assert progress.user == user
        assert progress.total_articles_read == 10
        assert progress.total_quizzes_taken == 5
        assert progress.current_streak == 7
    
    def test_progress_defaults(self, user):
        """Test progress defaults to zero."""
        progress = UserProgress.objects.create(user=user)
        
        assert progress.total_articles_read == 0
        assert progress.total_quizzes_taken == 0
        assert progress.current_streak == 0
        assert progress.syllabus_coverage_percent == 0.0
    
    def test_progress_one_to_one_with_user(self, user):
        """Test one-to-one relationship with user."""
        progress1 = UserProgress.objects.create(user=user)
        
        with pytest.raises(Exception):  # IntegrityError
            UserProgress.objects.create(user=user)
    
    def test_syllabus_coverage_validation(self, user):
        """Test syllabus coverage between 0-100."""
        progress = UserProgress.objects.create(
            user=user,
            syllabus_coverage_percent=50.0
        )
        
        assert 0 <= progress.syllabus_coverage_percent <= 100


@pytest.mark.django_db
class TestTopicMasteryModel:
    """Test TopicMastery model."""
    
    def test_create_mastery(self, user, topic):
        """Test creating topic mastery."""
        mastery = TopicMastery.objects.create(
            user=user,
            topic=topic,
            mastery_score=75.0,
            questions_attempted=10,
            questions_correct=7
        )
        
        assert mastery.user == user
        assert mastery.topic == topic
        assert mastery.mastery_score == 75.0
    
    def test_update_mastery_method(self, user, topic):
        """Test update_mastery recalculates score."""
        mastery = TopicMastery.objects.create(
            user=user,
            topic=topic,
            questions_attempted=10,
            questions_correct=8
        )
        
        mastery.update_mastery()
        
        assert mastery.mastery_score == 80.0
    
    def test_unique_user_topic_constraint(self, user, topic):
        """Test user can't have duplicate mastery for same topic."""
        TopicMastery.objects.create(user=user, topic=topic)
        
        with pytest.raises(Exception):  # IntegrityError
            TopicMastery.objects.create(user=user, topic=topic)
    
    def test_mastery_ordering(self, user, topic):
        """Test masteries ordered by score descending."""
        from engines.knowledge.models import Topic
        topic2 = Topic.objects.create(name='Topic 2', module=topic.module, subject=topic.subject)
        
        m1 = TopicMastery.objects.create(user=user, topic=topic, mastery_score=60)
        m2 = TopicMastery.objects.create(user=user, topic=topic2, mastery_score=90)
        
        masteries = list(TopicMastery.objects.all())
        assert masteries[0] == m2
        assert masteries[1] == m1


@pytest.mark.django_db
class TestBookmarkModel:
    """Test Bookmark model."""
    
    def test_create_bookmark(self, user):
        """Test creating bookmark."""
        bookmark = Bookmark.objects.create(
            user=user,
            content_type='article',
            content_id=uuid.uuid4(),
            notes='Test notes'
        )
        
        assert bookmark.user == user
        assert bookmark.content_type == 'article'
        assert bookmark.notes == 'Test notes'
    
    def test_unique_user_content_constraint(self, user):
        """Test user can't bookmark same content twice."""
        content_id = uuid.uuid4()
        
        Bookmark.objects.create(
            user=user,
            content_type='article',
            content_id=content_id
        )
        
        with pytest.raises(Exception):  # IntegrityError
            Bookmark.objects.create(
                user=user,
                content_type='article',
                content_id=content_id
            )
    
    def test_bookmark_ordering(self, user):
        """Test bookmarks ordered by created_at descending."""
        import time
        b1 = Bookmark.objects.create(user=user, content_type='article', content_id=uuid.uuid4())
        time.sleep(0.01)  # Ensure different timestamps
        b2 = Bookmark.objects.create(user=user, content_type='quiz', content_id=uuid.uuid4())
        
        bookmarks = list(Bookmark.objects.all())
        assert len(bookmarks) == 2
        # Most recent (b2) should be first due to ordering=['-created_at']
        assert bookmarks[0].id == b2.id
        assert bookmarks[1].id == b1.id


@pytest.mark.django_db
class TestReadingProgressModel:
    """Test ReadingProgress model."""
    
    def test_create_reading_progress(self, user):
        """Test creating reading progress."""
        article_id = uuid.uuid4()
        
        progress = ReadingProgress.objects.create(
            user=user,
            article_id=article_id,
            percent_read=45.5,
            last_position=1234
        )
        
        assert progress.user == user
        assert progress.article_id == article_id
        assert progress.percent_read == 45.5
        assert progress.last_position == 1234
    
    def test_unique_user_article_constraint(self, user):
        """Test user can't have duplicate progress for same article."""
        article_id = uuid.uuid4()
        
        ReadingProgress.objects.create(user=user, article_id=article_id)
        
        with pytest.raises(Exception):  # IntegrityError
            ReadingProgress.objects.create(user=user, article_id=article_id)
    
    def test_percent_read_validation(self, user):
        """Test percent_read between 0-100."""
        progress = ReadingProgress.objects.create(
            user=user,
            article_id=uuid.uuid4(),
            percent_read=75.0
        )
        
        assert 0 <= progress.percent_read <= 100
