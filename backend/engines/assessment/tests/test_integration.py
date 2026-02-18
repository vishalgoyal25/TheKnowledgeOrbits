"""
Assessment Engine - Integration Tests

End-to-end quiz workflows.
"""

import pytest
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
from rest_framework import status
from engines.assessment.models import Quiz, Question, QuizAttempt, QuestionResponse
from engines.auth.models import User
from engines.knowledge.models import Program, Subject, Module, Topic


@pytest.fixture
def authenticated_user():
    """Authenticated user and client."""
    user = User.objects.create_user(email='test@test.com', password='pass')
    user.is_verified = True
    user.save()
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.fixture
def topic():
    """Create topic with full hierarchy."""
    program = Program.objects.create(name='UPSC CSE')
    subject = Subject.objects.create(name='Test', program=program)
    module = Module.objects.create(name='Test Module', subject=subject)
    return Topic.objects.create(name='Test Topic', module=module, subject=subject)


@pytest.mark.django_db
class TestCompleteQuizFlow:
    """Test complete quiz workflow."""
    
    def test_start_take_submit_flow(self, authenticated_user, topic):
        """Test: Start → Take → Submit flow."""
        client, user = authenticated_user
        
        # Create quiz with questions
        quiz = Quiz.objects.create(
            title='Complete Flow Quiz',
            topic=topic,
            question_count=3,
            is_active=True
        )
        
        questions = []
        for i in range(3):
            q = Question.objects.create(
                quiz=quiz,
                question_text=f'Question {i+1}',
                options={'A': 'Correct', 'B': 'Wrong', 'C': 'Wrong', 'D': 'Wrong'},
                correct_answer='A',
                explanation=f'Explanation {i+1}',
                order_index=i
            )
            questions.append(q)
        
        # Step 1: Start quiz
        response = client.post(f'/api/v1/assessment/quizzes/{quiz.id}/start/')
        assert response.status_code == status.HTTP_201_CREATED
        attempt_id = response.data['id']
        
        # Verify attempt created
        assert QuizAttempt.objects.filter(id=attempt_id).exists()
        
        # Step 2: Submit quiz (all correct)
        answers = [
            {'question_id': str(q.id), 'selected_option': 'A'}
            for q in questions
        ]
        
        response = client.post('/api/v1/assessment/submit/', {
            'attempt_id': attempt_id,
            'answers': answers
        }, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['score'] == 100.0
        assert response.data['correct_count'] == 3
        assert response.data['wrong_count'] == 0
        
        # Step 3: Verify attempt updated
        attempt = QuizAttempt.objects.get(id=attempt_id)
        assert attempt.status == 'submitted'
        assert attempt.score == 100.0
        
        # Step 4: Verify responses created
        responses = QuestionResponse.objects.filter(attempt_id=attempt_id)
        assert responses.count() == 3
        assert all(r.is_correct for r in responses)


@pytest.mark.django_db
class TestPrivateQuizWorkflow:
    """Test private quiz (My Quizzes) workflow."""
    
    @patch('engines.assessment.views.get_quiz_generator')
    def test_private_quiz_visibility(self, mock_get_generator, authenticated_user, topic):
        """Test private quizzes only visible to owner."""
        client, user = authenticated_user
        
        # Create quiz that mock will "generate"
        quiz = Quiz.objects.create(
            title='Private Quiz',
            topic=topic,
            is_active=True,
            question_count=10
        )
        
        mock_generator = MagicMock()
        mock_generator.generate_quiz.return_value = quiz
        mock_get_generator.return_value = mock_generator
        
        response = client.post('/api/v1/assessment/generate/', {
            'topic_id': str(topic.id),
            'difficulty': 'medium',
            'include_ca': False,
            'question_count': 10
        })
        
        assert response.status_code == status.HTTP_201_CREATED
        
        # Check in My Quizzes
        response = client.get('/api/v1/assessment/my-quizzes/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
        
        # Check not visible to anonymous
        client.logout()
        response = client.get('/api/v1/assessment/quizzes/')
        assert response.status_code == status.HTTP_200_OK
        private_quizzes = [q for q in response.data if q['id'] == str(quiz.id)]
        assert len(private_quizzes) == 0
