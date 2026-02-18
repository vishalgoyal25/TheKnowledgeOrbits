"""
Shared Services - Visibility Service Tests

Tests for VisibilityService (public/private content filtering).
"""

import pytest
from django.db.models import Q
from engines.shared.services.visibility_service import VisibilityService, get_visibility_service
from engines.auth.models import User
from engines.article_generation.models import Article
from engines.assessment.models import Quiz
from engines.knowledge.models import Program, Subject, Module, Topic


@pytest.fixture
def user1():
    """Create first test user."""
    return User.objects.create_user(email='user1@test.com', password='pass')


@pytest.fixture
def user2():
    """Create second test user."""
    return User.objects.create_user(email='user2@test.com', password='pass')


@pytest.fixture
def topic():
    """Create test topic."""
    program = Program.objects.create(name='UPSC CSE')
    subject = Subject.objects.create(name='Polity', program=program)
    module = Module.objects.create(name='Constitution', subject=subject)
    return Topic.objects.create(name='Article 370', module=module, subject=subject)


@pytest.fixture
def articles(user1, user2, topic):
    """Create test articles with different visibility."""
    return {
        'public1': Article.objects.create(
            title='Public Article 1',
            topic=topic,
            is_public=True,
            created_by=None  # System-owned
        ),
        'public2': Article.objects.create(
            title='Public Article 2',
            topic=topic,
            is_public=True,
            created_by=user1  # User-owned but public
        ),
        'private_user1': Article.objects.create(
            title='Private Article User1',
            topic=topic,
            is_public=False,
            created_by=user1
        ),
        'private_user2': Article.objects.create(
            title='Private Article User2',
            topic=topic,
            is_public=False,
            created_by=user2
        )
    }


@pytest.fixture
def quizzes(user1, user2, topic):
    """Create test quizzes with different visibility."""
    return {
        'public1': Quiz.objects.create(
            title='Public Quiz 1',
            topic=topic,
            question_count=10,
            is_public=True,
            created_by=None
        ),
        'private_user1': Quiz.objects.create(
            title='Private Quiz User1',
            topic=topic,
            question_count=10,
            is_public=False,
            created_by=user1
        ),
        'private_user2': Quiz.objects.create(
            title='Private Quiz User2',
            topic=topic,
            question_count=10,
            is_public=False,
            created_by=user2
        )
    }


@pytest.mark.django_db
class TestVisibilityServiceArticles:
    """Test VisibilityService for articles."""
    
    def test_anonymous_sees_only_public(self, articles):
        """Test anonymous user sees only public articles."""
        service = VisibilityService()
        queryset = Article.objects.all()
        
        filtered = service.filter_articles(queryset, user=None)
        
        assert filtered.count() == 2  # Both public articles
        assert articles['public1'] in filtered
        assert articles['public2'] in filtered
        assert articles['private_user1'] not in filtered
        assert articles['private_user2'] not in filtered
    
    def test_user_sees_public_and_own_private(self, user1, articles):
        """Test authenticated user sees public + own private."""
        service = VisibilityService()
        queryset = Article.objects.all()
        
        filtered = service.filter_articles(queryset, user=user1)
        
        assert filtered.count() == 3  # 2 public + 1 own private
        assert articles['public1'] in filtered
        assert articles['public2'] in filtered
        assert articles['private_user1'] in filtered
        assert articles['private_user2'] not in filtered  # Other user's private
    
    def test_user_does_not_see_other_private(self, user1, articles):
        """Test user cannot see other user's private articles."""
        service = VisibilityService()
        queryset = Article.objects.all()
        
        filtered = service.filter_articles(queryset, user=user1)
        
        assert articles['private_user2'] not in filtered
    
    def test_can_access_public_article_anonymous(self, articles):
        """Test anonymous user can access public article."""
        service = VisibilityService()
        
        assert service.can_access_article(articles['public1'], user=None)
    
    def test_cannot_access_private_article_anonymous(self, articles):
        """Test anonymous user cannot access private article."""
        service = VisibilityService()
        
        assert not service.can_access_article(articles['private_user1'], user=None)
    
    def test_can_access_own_private_article(self, user1, articles):
        """Test user can access own private article."""
        service = VisibilityService()
        
        assert service.can_access_article(articles['private_user1'], user=user1)
    
    def test_cannot_access_other_private_article(self, user1, articles):
        """Test user cannot access other user's private article."""
        service = VisibilityService()
        
        assert not service.can_access_article(articles['private_user2'], user=user1)


@pytest.mark.django_db
class TestVisibilityServiceQuizzes:
    """Test VisibilityService for quizzes."""
    
    def test_anonymous_sees_only_public_quizzes(self, quizzes):
        """Test anonymous user sees only public quizzes."""
        service = VisibilityService()
        queryset = Quiz.objects.all()
        
        filtered = service.filter_quizzes(queryset, user=None)
        
        assert filtered.count() == 1  # Only public quiz
        assert quizzes['public1'] in filtered
        assert quizzes['private_user1'] not in filtered
        assert quizzes['private_user2'] not in filtered
    
    def test_user_sees_public_and_own_private_quizzes(self, user1, quizzes):
        """Test authenticated user sees public + own private quizzes."""
        service = VisibilityService()
        queryset = Quiz.objects.all()
        
        filtered = service.filter_quizzes(queryset, user=user1)
        
        assert filtered.count() == 2  # 1 public + 1 own private
        assert quizzes['public1'] in filtered
        assert quizzes['private_user1'] in filtered
        assert quizzes['private_user2'] not in filtered
    
    def test_can_access_public_quiz_anonymous(self, quizzes):
        """Test anonymous user can access public quiz."""
        service = VisibilityService()
        
        assert service.can_access_quiz(quizzes['public1'], user=None)
    
    def test_cannot_access_private_quiz_anonymous(self, quizzes):
        """Test anonymous user cannot access private quiz."""
        service = VisibilityService()
        
        assert not service.can_access_quiz(quizzes['private_user1'], user=None)
    
    def test_can_access_own_private_quiz(self, user1, quizzes):
        """Test user can access own private quiz."""
        service = VisibilityService()
        
        assert service.can_access_quiz(quizzes['private_user1'], user=user1)
    
    def test_cannot_access_other_private_quiz(self, user1, quizzes):
        """Test user cannot access other user's private quiz."""
        service = VisibilityService()
        
        assert not service.can_access_quiz(quizzes['private_user2'], user=user1)


@pytest.mark.django_db
class TestVisibilityServiceSingleton:
    """Test VisibilityService singleton pattern."""
    
    def test_get_visibility_service_returns_instance(self):
        """Test get_visibility_service returns instance."""
        service = get_visibility_service()
        
        assert isinstance(service, VisibilityService)
    
    def test_get_visibility_service_returns_same_instance(self):
        """Test get_visibility_service returns same instance (singleton)."""
        service1 = get_visibility_service()
        service2 = get_visibility_service()
        
        assert service1 is service2


@pytest.mark.django_db
class TestVisibilityServiceEdgeCases:
    """Test edge cases for VisibilityService."""
    
    def test_filter_empty_queryset(self):
        """Test filtering empty queryset."""
        service = VisibilityService()
        queryset = Article.objects.none()
        
        filtered = service.filter_articles(queryset, user=None)
        
        assert filtered.count() == 0
    
    def test_filter_with_unauthenticated_user(self, articles):
        """Test filtering with explicitly unauthenticated user."""
        from django.contrib.auth.models import AnonymousUser
        
        service = VisibilityService()
        queryset = Article.objects.all()
        
        anonymous = AnonymousUser()
        filtered = service.filter_articles(queryset, user=anonymous)
        
        # Should see only public articles
        assert filtered.count() == 2
    
    def test_can_access_with_none_user(self, articles):
        """Test can_access with None user (anonymous)."""
        service = VisibilityService()
        
        # Public accessible
        assert service.can_access_article(articles['public1'], user=None)
        
        # Private not accessible
        assert not service.can_access_article(articles['private_user1'], user=None)
    
    def test_system_owned_public_article(self, topic):
        """Test system-owned (created_by=None) public article."""
        service = VisibilityService()
        
        article = Article.objects.create(
            title='System Article',
            topic=topic,
            is_public=True,
            created_by=None
        )
        
        # Accessible to anonymous
        assert service.can_access_article(article, user=None)
    
    def test_multiple_users_same_queryset(self, user1, user2, articles):
        """Test filtering same queryset for different users."""
        service = VisibilityService()
        queryset = Article.objects.all()
        
        # User1 sees their private
        filtered1 = service.filter_articles(queryset, user=user1)
        assert articles['private_user1'] in filtered1
        assert articles['private_user2'] not in filtered1
        
        # User2 sees their private
        filtered2 = service.filter_articles(queryset, user=user2)
        assert articles['private_user2'] in filtered2
        assert articles['private_user1'] not in filtered2

