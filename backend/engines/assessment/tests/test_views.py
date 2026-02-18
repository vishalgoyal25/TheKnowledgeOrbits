"""
Assessment Engine - View Tests

Tests for quiz generation and attempt endpoints.
"""

import pytest
import uuid
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
from rest_framework import status
from engines.assessment.models import Quiz, Question, QuizAttempt
from engines.auth.models import User
from engines.knowledge.models import Program, Subject, Module, Topic


@pytest.fixture
def api_client():
    """API client fixture."""
    return APIClient()


@pytest.fixture
def user():
    """Create test user."""
    user = User.objects.create_user(email='test@test.com', password='pass')
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
    program = Program.objects.create(name='UPSC CSE')
    subject = Subject.objects.create(name='Test', program=program)
    module = Module.objects.create(name='Test Module', subject=subject)
    return Topic.objects.create(name='Test Topic', module=module, subject=subject)


@pytest.mark.django_db
class TestQuizListView:
    """Test quiz list endpoint."""
    
    def test_list_public_quizzes(self, api_client, topic):
        """Test listing public quizzes."""
        Quiz.objects.create(
            title='Public Quiz 1',
            topic=topic,
            is_public=True,
            is_active=True
        )
        Quiz.objects.create(
            title='Public Quiz 2',
            topic=topic,
            is_public=True,
            is_active=True
        )
        
        response = api_client.get('/api/v1/assessment/quizzes/')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
    
    def test_inactive_quizzes_hidden(self, api_client, topic):
        """Test inactive quizzes not shown."""
        Quiz.objects.create(
            title='Inactive Quiz',
            topic=topic,
            is_public=True,
            is_active=False
        )
        
        response = api_client.get('/api/v1/assessment/quizzes/')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0


@pytest.mark.django_db
class TestQuizGenerateView:
    """Test quiz generation endpoint."""
    
    @patch('engines.assessment.views.get_quiz_generator')
    def test_generate_quiz_authenticated(self, mock_get_generator, authenticated_client, topic):
        """Test authenticated user generates private quiz."""
        client, user = authenticated_client
        
        # Create quiz that mock will "generate"
        quiz = Quiz.objects.create(
            title='Generated Quiz',
            topic=topic,
            question_count=10,
            is_active=True
        )
        
        mock_generator = MagicMock()
        mock_generator.generate_quiz.return_value = quiz
        mock_get_generator.return_value = mock_generator
        
        data = {
            'topic_id': str(topic.id),
            'difficulty': 'medium',
            'include_ca': False,
            'question_count': 10
        }
        
        response = client.post('/api/v1/assessment/generate/', data)
        
        assert response.status_code == status.HTTP_201_CREATED
        # generate_quiz view returns QuizDetailSerializer data directly
        assert response.data['title'] == 'Generated Quiz'
    
    @patch('engines.assessment.views.get_quiz_generator')
    def test_generate_quiz_invalid_topic(self, mock_get_generator, authenticated_client):
        """Test generation fails with invalid topic."""
        client, user = authenticated_client
        
        mock_generator = MagicMock()
        mock_generator.generate_quiz.side_effect = ValueError("Topic not found")
        mock_get_generator.return_value = mock_generator
        
        data = {
            'topic_id': str(uuid.uuid4()),
            'difficulty': 'medium',
            'include_ca': False,
            'question_count': 10
        }
        
        response = client.post('/api/v1/assessment/generate/', data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestQuizStartView:
    """Test quiz start endpoint."""
    
    def test_start_quiz(self, authenticated_client, topic):
        """Test starting a quiz."""
        client, user = authenticated_client
        
        quiz = Quiz.objects.create(
            title='Test Quiz',
            topic=topic,
            question_count=5,
            is_active=True
        )
        
        # Add questions
        for i in range(5):
            Question.objects.create(
                quiz=quiz,
                question_text=f'Question {i+1}',
                options={'A': '1', 'B': '2', 'C': '3', 'D': '4'},
                correct_answer='A',
                explanation='Test explanation',
                order_index=i
            )
        
        response = client.post(f'/api/v1/assessment/quizzes/{quiz.id}/start/')
        
        assert response.status_code == status.HTTP_201_CREATED
        # QuizAttemptSerializer returns 'id' not 'attempt_id'
        assert 'id' in response.data
        
        # Verify attempt created
        attempt_id = response.data['id']
        assert QuizAttempt.objects.filter(id=attempt_id, user=user).exists()


@pytest.mark.django_db
class TestQuizSubmitView:
    """Test quiz submission endpoint."""
    
    def test_submit_quiz_all_correct(self, authenticated_client, topic):
        """Test submitting quiz with all correct answers."""
        client, user = authenticated_client
        
        quiz = Quiz.objects.create(title='Quiz', topic=topic, question_count=3)
        questions = []
        for i in range(3):
            q = Question.objects.create(
                quiz=quiz,
                question_text=f'Q{i+1}',
                options={'A': 'Correct', 'B': 'Wrong'},
                correct_answer='A',
                explanation='Test',
                order_index=i
            )
            questions.append(q)
        
        attempt = QuizAttempt.objects.create(quiz=quiz, user=user, status='active')
        
        data = {
            'attempt_id': str(attempt.id),
            'answers': [
                {'question_id': str(q.id), 'selected_option': 'A'}
                for q in questions
            ]
        }
        
        response = client.post('/api/v1/assessment/submit/', data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['score'] == 100.0
        assert response.data['correct_count'] == 3
        assert response.data['wrong_count'] == 0
    
    def test_submit_quiz_partial_correct(self, authenticated_client, topic):
        """Test submitting quiz with mixed answers."""
        client, user = authenticated_client
        
        quiz = Quiz.objects.create(title='Quiz', topic=topic, question_count=2)
        q1 = Question.objects.create(
            quiz=quiz,
            question_text='Q1',
            options={'A': 'Correct', 'B': 'Wrong'},
            correct_answer='A',
            explanation='Test',
            order_index=0
        )
        q2 = Question.objects.create(
            quiz=quiz,
            question_text='Q2',
            options={'A': 'Wrong', 'B': 'Correct'},
            correct_answer='B',
            explanation='Test',
            order_index=1
        )
        
        attempt = QuizAttempt.objects.create(quiz=quiz, user=user, status='active')
        
        data = {
            'attempt_id': str(attempt.id),
            'answers': [
                {'question_id': str(q1.id), 'selected_option': 'A'},  # Correct
                {'question_id': str(q2.id), 'selected_option': 'A'},  # Wrong
            ]
        }
        
        response = client.post('/api/v1/assessment/submit/', data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['score'] == 50.0
        assert response.data['correct_count'] == 1
        assert response.data['wrong_count'] == 1
