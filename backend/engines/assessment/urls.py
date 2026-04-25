"""
Assessment Engine URLs
"""

from django.urls import path

from engines.assessment import views

app_name = "assessment"

urlpatterns = [
    # Quiz generation
    path("generate/", views.generate_quiz, name="generate-quiz"),
    path(
        "jobs/<str:job_id>/status/", views.get_quiz_job_status, name="quiz-job-status"
    ),
    # Quiz listing and details
    path("quizzes/", views.list_quizzes, name="list-quizzes"),
    path("quizzes/<uuid:quiz_id>/", views.get_quiz, name="get-quiz"),
    # Quiz taking
    path("quizzes/<uuid:quiz_id>/start/", views.start_quiz, name="start-quiz"),
    path("submit/", views.submit_quiz, name="submit-quiz"),
    # Attempts
    path("attempts/<uuid:attempt_id>/", views.get_attempt_result, name="get-attempt"),
    path("my-attempts/", views.list_user_attempts, name="my-attempts"),
    path("my-quizzes/", views.my_quizzes, name="my-quizzes"),
    # Daily Public Quiz — no auth required
    path(
        "public/daily/", views.daily_public_quiz_today, name="daily-public-quiz-today"
    ),
]
