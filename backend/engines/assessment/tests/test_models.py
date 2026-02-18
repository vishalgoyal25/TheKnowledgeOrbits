"""
Assessment Engine - Model Tests

Tests for Quiz, Question, QuizAttempt, QuestionResponse models.
"""

import pytest
import uuid
from django.utils import timezone
from engines.assessment.models import Quiz, Question, QuizAttempt, QuestionResponse
from engines.auth.models import User
from engines.knowledge.models import Program, Subject, Module, Topic


@pytest.fixture
def user():
    """Create test user."""
    return User.objects.create_user(email='test@test.com', password='pass')


@pytest.fixture
def topic():
    """Create test topic with full hierarchy."""
    program = Program.objects.create(name='UPSC CSE')
    subject = Subject.objects.create(name='Test Subject', program=program)
    module = Module.objects.create(name='Test Module', subject=subject)
    return Topic.objects.create(name='Test Topic', module=module, subject=subject)


@pytest.mark.django_db
class TestQuizModel:
    """Test Quiz model."""
    
    def test_create_quiz(self, topic):
        """Test creating quiz."""
        quiz = Quiz.objects.create(
            title='UPSC Polity Quiz',
            topic=topic,
            difficulty_level='medium',
            question_count=10,
            time_limit=1800
        )
        
        assert quiz.title == 'UPSC Polity Quiz'
        assert quiz.topic == topic
        assert quiz.difficulty_level == 'medium'
        assert quiz.question_count == 10
    
    def test_quiz_has_uuid(self, topic):
        """Test quiz has UUID primary key."""
        quiz = Quiz.objects.create(title='Test Quiz', topic=topic)
        
        assert isinstance(quiz.id, uuid.UUID)
        assert len(str(quiz.id)) == 36
    
    def test_quiz_ownership_fields(self, topic, user):
        """Test ownership extension fields."""
        quiz = Quiz.objects.create(
            title='User Quiz',
            topic=topic,
            created_by=user,
            is_public=False
        )
        
        assert quiz.created_by == user
        assert not quiz.is_public
        assert quiz.is_user_owned
    
    def test_is_user_owned_property(self, topic, user):
        """Test is_user_owned property."""
        # User-owned quiz
        quiz1 = Quiz.objects.create(
            title='Private Quiz',
            topic=topic,
            created_by=user
        )
        assert quiz1.is_user_owned
        
        # System quiz
        quiz2 = Quiz.objects.create(
            title='Public Quiz',
            topic=topic,
            created_by=None
        )
        assert not quiz2.is_user_owned
    
    def test_include_ca_flag(self, topic):
        """Test include_ca flag."""
        quiz = Quiz.objects.create(
            title='Hybrid Quiz',
            topic=topic,
            include_ca=True
        )
        
        assert quiz.include_ca
        assert '[CA]' in str(quiz)


@pytest.mark.django_db
class TestQuestionModel:
    """Test Question model."""
    
    def test_create_question(self, topic):
        """Test creating question."""
        quiz = Quiz.objects.create(title='Quiz', topic=topic)
        
        question = Question.objects.create(
            quiz=quiz,
            question_text='What is the capital of India?',
            question_type='single_mcq',
            options={'A': 'Mumbai', 'B': 'Delhi', 'C': 'Kolkata', 'D': 'Chennai'},
            correct_answer='B',
            explanation='New Delhi is the capital of India.',
            difficulty_level='easy',
            order_index=0
        )
        
        assert question.question_text == 'What is the capital of India?'
        assert question.correct_answer == 'B'
        assert question.options['B'] == 'Delhi'
    
    def test_multi_statement_question(self, topic):
        """Test multi-statement question type."""
        quiz = Quiz.objects.create(title='Quiz', topic=topic)
        
        question = Question.objects.create(
            quiz=quiz,
            question_text='Which of the following are correct?',
            question_type='multi_statement',
            statements=[
                '1. Statement one is true',
                '2. Statement two is false',
                '3. Statement three is true'
            ],
            options={
                'A': '1 and 2 only',
                'B': '1 and 3 only',
                'C': '2 and 3 only',
                'D': 'All of the above'
            },
            correct_answer='B',
            explanation='Statements 1 and 3 are correct.',
            order_index=0
        )
        
        assert question.question_type == 'multi_statement'
        assert len(question.statements) == 3
    
    def test_question_ordering(self, topic):
        """Test questions ordered by order_index."""
        quiz = Quiz.objects.create(title='Quiz', topic=topic)
        
        q3 = Question.objects.create(
            quiz=quiz,
            question_text='Q3',
            options={'A': '1', 'B': '2'},
            correct_answer='A',
            explanation='Test',
            order_index=2
        )
        q1 = Question.objects.create(
            quiz=quiz,
            question_text='Q1',
            options={'A': '1', 'B': '2'},
            correct_answer='A',
            explanation='Test',
            order_index=0
        )
        
        questions = list(quiz.questions.all())
        assert questions[0] == q1
        assert questions[1] == q3


@pytest.mark.django_db
class TestQuizAttemptModel:
    """Test QuizAttempt model."""
    
    def test_create_attempt(self, topic, user):
        """Test creating quiz attempt."""
        quiz = Quiz.objects.create(title='Quiz', topic=topic)
        
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            user=user,
            status='active'
        )
        
        assert attempt.quiz == quiz
        assert attempt.user == user
        assert attempt.status == 'active'
    
    def test_accuracy_property(self, topic, user):
        """Test accuracy calculation."""
        quiz = Quiz.objects.create(title='Quiz', topic=topic)
        
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            user=user,
            correct_count=8,
            wrong_count=2,
            unanswered_count=0
        )
        
        assert attempt.accuracy == 80.0
    
    def test_accuracy_with_no_answers(self, topic, user):
        """Test accuracy when no questions answered."""
        quiz = Quiz.objects.create(title='Quiz', topic=topic)
        
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            user=user,
            correct_count=0,
            wrong_count=0
        )
        
        assert attempt.accuracy == 0.0
    
    def test_guest_mode_attempt(self, topic):
        """Test quiz attempt without user (guest mode)."""
        quiz = Quiz.objects.create(title='Quiz', topic=topic)
        
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            user=None,
            status='active'
        )
        
        assert attempt.user is None
        assert 'Guest' in str(attempt)


@pytest.mark.django_db
class TestQuestionResponseModel:
    """Test QuestionResponse model."""
    
    def test_create_response(self, topic, user):
        """Test creating question response."""
        quiz = Quiz.objects.create(title='Quiz', topic=topic)
        question = Question.objects.create(
            quiz=quiz,
            question_text='Test?',
            options={'A': 'Yes', 'B': 'No'},
            correct_answer='A',
            explanation='Test'
        )
        attempt = QuizAttempt.objects.create(quiz=quiz, user=user)
        
        response = QuestionResponse.objects.create(
            attempt=attempt,
            question=question,
            selected_option='A',
            is_correct=True,
            time_spent=30
        )
        
        assert response.selected_option == 'A'
        assert response.is_correct
        assert response.time_spent == 30
    
    def test_unique_attempt_question_constraint(self, topic, user):
        """Test user can't answer same question twice in attempt."""
        quiz = Quiz.objects.create(title='Quiz', topic=topic)
        question = Question.objects.create(
            quiz=quiz,
            question_text='Test?',
            options={'A': '1', 'B': '2'},
            correct_answer='A',
            explanation='Test'
        )
        attempt = QuizAttempt.objects.create(quiz=quiz, user=user)
        
        QuestionResponse.objects.create(
            attempt=attempt,
            question=question,
            selected_option='A'
        )
        
        with pytest.raises(Exception):  # IntegrityError
            QuestionResponse.objects.create(
                attempt=attempt,
                question=question,
                selected_option='B'
            )
    
    def test_unanswered_response(self, topic, user):
        """Test unanswered question (blank selected_option)."""
        quiz = Quiz.objects.create(title='Quiz', topic=topic)
        question = Question.objects.create(
            quiz=quiz,
            question_text='Test?',
            options={'A': '1', 'B': '2'},
            correct_answer='A',
            explanation='Test'
        )
        attempt = QuizAttempt.objects.create(quiz=quiz, user=user)
        
        response = QuestionResponse.objects.create(
            attempt=attempt,
            question=question,
            selected_option='',
            is_correct=False
        )
        
        assert response.selected_option == ''
        assert not response.is_correct
        assert 'Unanswered' in str(response)
