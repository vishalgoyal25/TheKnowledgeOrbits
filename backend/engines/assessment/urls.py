"""
Assessment Engine URLs
"""

from django.urls import path
from engines.assessment import views

app_name = 'assessment'

urlpatterns = [
    # Quiz generation
    path(
        'generate/',
        views.generate_quiz,
        name='generate-quiz'
    ),
    
    # Quiz listing and details
    path(
        'quizzes/',
        views.list_quizzes,
        name='list-quizzes'
    ),
    path(
        'quizzes/<uuid:quiz_id>/',
        views.get_quiz,
        name='get-quiz'
    ),
    
    # Quiz taking
    path(
        'quizzes/<uuid:quiz_id>/start/',
        views.start_quiz,
        name='start-quiz'
    ),
    path(
        'submit/',
        views.submit_quiz,
        name='submit-quiz'
    ),
    
    # Attempts
    path(
        'attempts/<uuid:attempt_id>/',
        views.get_attempt_result,
        name='get-attempt'
    ),
    path(
        'my-attempts/',
        views.list_user_attempts,
        name='my-attempts'
    ),
    
]
