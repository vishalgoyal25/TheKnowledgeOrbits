import sentry_sdk

"""
Assessment Engine Views

API endpoints for quiz operations.
"""

from typing import cast

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

import structlog

from core.pagination import StandardPageNumberPagination
from engines.assessment.models import QuestionResponse, Quiz, QuizAttempt
from engines.assessment.serializers import (
    QuestionDetailSerializer,
    QuizAttemptSerializer,
    QuizDetailSerializer,
    QuizGenerateSerializer,
    QuizListSerializer,
    QuizSubmitSerializer,
)
from engines.assessment.services.quiz_generator import get_quiz_generator
from engines.auth.models import User
from engines.shared.services.visibility_service import get_visibility_service
from engines.userstate.services.activity_service import get_activity_service
from engines.userstate.services.mastery_service import get_mastery_service

logger = structlog.get_logger(__name__)


@api_view(["POST"])
@permission_classes([AllowAny])  # Allow generation without auth for testing
def generate_quiz(request: Request) -> Response:
    """
    Generate new quiz from topic.

    POST /api/v1/assessment/generate/
    Body: {
        "topic_id": "uuid",
        "difficulty": "medium",
        "include_ca": false,
        "question_count": 10
    }

    Returns:
        201: Quiz detail with questions
        400: Validation error
        500: Generation failed
    """
    serializer = QuizGenerateSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Get generator service
        generator = get_quiz_generator()

        # Generate quiz
        quiz = generator.generate_quiz(
            topic_id=str(serializer.validated_data["topic_id"]),
            difficulty=serializer.validated_data["difficulty"],
            include_ca=serializer.validated_data["include_ca"],
            question_count=serializer.validated_data["question_count"],
            user_id=request.user.id if request.user.is_authenticated else None,
        )

        # ===== OWNERSHIP LOGIC (PKB Extension) =====
        if request.user.is_authenticated:
            # User-owned private quiz
            user = cast(User, request.user)  # type: ignore
            quiz.created_by = user
            quiz.is_public = False
            quiz.save()
            logger.info(
                "private_quiz_generated", user_email=user.email, quiz_id=str(quiz.id)
            )
        else:
            # Public quiz
            quiz.is_public = True
            quiz.created_by = None
            quiz.save()
            logger.info("public_quiz_generated", quiz_id=str(quiz.id))
        # ===== END OWNERSHIP LOGIC =====

        # Serialize and return
        result = QuizDetailSerializer(quiz).data

        logger.info(
            "quiz_generation_success",
            quiz_id=str(quiz.id),
            user_id=request.user.id if request.user.is_authenticated else None,
        )

        return Response(result, status=status.HTTP_201_CREATED)

    except ValueError as e:
        logger.warning("quiz_generation_validation_error", error=str(e))
        return Response(
            {"error": "VALIDATION_ERROR", "message": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.error("quiz_generation_failed", error=str(e), exc_info=True)
        return Response(
            {"error": "GENERATION_FAILED", "message": "Failed to generate quiz"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def list_quizzes(request: Request) -> Response:
    """
    List available quizzes with filters.

    GET /api/v1/assessment/quizzes/
    Query params:
        - topic_id: UUID (optional)
        - difficulty: easy|medium|hard (optional)
        - include_ca: true|false (optional)

    Returns:
        200: List of quizzes
    """
    queryset = Quiz.objects.filter(is_active=True)

    # ===== VISIBILITY FILTERING (PKB Ownership Logic) =====
    visibility_service = get_visibility_service()

    # We only apply filtering if the user is authenticated since AnonymousUser might not be expected
    user = cast(User, request.user) if request.user.is_authenticated else None  # type: ignore
    queryset = visibility_service.filter_quizzes(queryset, user)
    # ===== END FILTERING =====

    # Apply filters
    topic_id = request.query_params.get("topic_id")
    if topic_id:
        queryset = queryset.filter(topic_id=topic_id)

    difficulty = request.query_params.get("difficulty")
    if difficulty:
        queryset = queryset.filter(difficulty_level=difficulty)

    include_ca = request.query_params.get("include_ca")
    if include_ca is not None:
        include_ca_bool = include_ca.lower() == "true"
        queryset = queryset.filter(include_ca=include_ca_bool)

    # Prefetch related data
    quizzes = queryset.select_related("topic").order_by("-created_at")

    paginator = StandardPageNumberPagination()
    paginated_quizzes = paginator.paginate_queryset(quizzes, request)
    serializer = QuizListSerializer(paginated_quizzes, many=True)
    return paginator.get_paginated_response(serializer.data)


# Add new view for "My Quizzes"
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_quizzes(request: Request) -> Response:
    """
    Get user's private quizzes.

    GET /api/v1/assessment/my-quizzes/
    """
    user = cast(User, request.user)
    quizzes = (
        Quiz.objects.filter(created_by=user, is_public=False)
        .select_related("topic")
        .order_by("-created_at")
    )

    paginator = StandardPageNumberPagination()
    paginated_quizzes = paginator.paginate_queryset(quizzes, request)
    serializer = QuizListSerializer(paginated_quizzes, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_quiz(request: Request, quiz_id: str) -> Response:
    """
    Get quiz details WITHOUT correct answers.

    GET /api/v1/assessment/quizzes/{quiz_id}/

    Returns:
        200: Quiz detail with questions (no answers)
        404: Quiz not found
    """
    quiz = get_object_or_404(
        Quiz.objects.prefetch_related("questions").select_related("topic"),
        id=quiz_id,
        is_active=True,
    )

    serializer = QuizDetailSerializer(quiz)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([AllowAny])
def start_quiz(request: Request, quiz_id: str) -> Response:
    """
    Start a new quiz attempt.

    POST /api/v1/assessment/quizzes/{quiz_id}/start/

    Returns:
        201: Attempt created
        404: Quiz not found
        409: Active attempt already exists
    """
    quiz = get_object_or_404(Quiz, id=quiz_id, is_active=True)

    # Check for existing active attempt (for authenticated users)
    if request.user.is_authenticated:
        active_attempt = QuizAttempt.objects.filter(
            quiz=quiz, user=request.user, status="active"
        ).first()

        if active_attempt:
            # If user wants to restart, we should mark the old one as abandoned
            active_attempt.status = "abandoned"
            active_attempt.save()
            logger.info(
                "stale_attempt_abandoned",
                attempt_id=str(active_attempt.id),
                quiz_id=quiz_id,
                user_email=request.user.email,
            )

    # Create new attempt
    attempt = QuizAttempt.objects.create(
        quiz=quiz,
        user=request.user if request.user.is_authenticated else None,
        status="active",
    )

    logger.info(
        "quiz_attempt_started",
        attempt_id=str(attempt.id),
        quiz_id=str(quiz_id),
        user_id=request.user.id if request.user.is_authenticated else None,
    )

    serializer = QuizAttemptSerializer(attempt)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
@transaction.atomic
def submit_quiz(request: Request) -> Response:
    """
    Submit quiz attempt with answers.

    POST /api/v1/assessment/submit/
    Body: {
        "attempt_id": "uuid",
        "answers": [
            {
                "question_id": "uuid",
                "selected_option": "A",
                "time_spent": 45,
                "marked_for_review": false
            }
        ]
    }

    Returns:
        200: Graded results with explanations
        400: Validation error
        404: Attempt not found
        409: Attempt already submitted
    """
    serializer = QuizSubmitSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    attempt_id = serializer.validated_data["attempt_id"]
    answers = serializer.validated_data["answers"]

    # Get attempt
    attempt = get_object_or_404(QuizAttempt, id=attempt_id)

    # Check if attempt belongs to user (for authenticated users)
    if request.user.is_authenticated and attempt.user != request.user:
        return Response(
            {"error": "FORBIDDEN", "message": "This attempt does not belong to you"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check if already submitted
    if attempt.status != "active":
        return Response(
            {
                "error": "ALREADY_SUBMITTED",
                "message": "This attempt is already submitted",
            },
            status=status.HTTP_409_CONFLICT,
        )

    # Process answers
    correct_count = 0
    wrong_count = 0
    unanswered_count = 0
    total_time = 0

    # Create answer map
    answer_map = {str(answer["question_id"]): answer for answer in answers}

    # Process each question
    questions = attempt.quiz.questions.all()
    responses = []

    for question in questions:
        answer_data = answer_map.get(str(question.id))

        if answer_data:
            selected_option = answer_data.get("selected_option", "").strip()
            time_spent = answer_data.get("time_spent", 0)
            marked = answer_data.get("marked_for_review", False)

            # Check correctness
            is_correct = (
                (selected_option == question.correct_answer)
                if selected_option
                else False
            )

            if selected_option:
                if is_correct:
                    correct_count += 1
                else:
                    wrong_count += 1
            else:
                unanswered_count += 1

            total_time += time_spent

            # Create response record
            resp = QuestionResponse.objects.create(
                attempt=attempt,
                question=question,
                selected_option=selected_option,
                is_correct=is_correct,
                time_spent=time_spent,
                marked_for_review=marked,
                answered_at=timezone.now() if selected_option else None,
            )
            responses.append(resp)
        else:
            # Question not answered
            unanswered_count += 1
            resp = QuestionResponse.objects.create(
                attempt=attempt,
                question=question,
                selected_option="",
                is_correct=False,
                time_spent=0,
            )
            responses.append(resp)

    # Calculate score
    total_questions = attempt.quiz.question_count
    score = (correct_count / total_questions * 100) if total_questions > 0 else 0

    # Update attempt
    attempt.status = "submitted"
    attempt.score = score
    attempt.correct_count = correct_count
    attempt.wrong_count = wrong_count
    attempt.unanswered_count = unanswered_count
    attempt.submitted_at = timezone.now()
    attempt.time_spent = total_time
    attempt.save()

    if request.user.is_authenticated:
        # Update topic mastery for each question
        mastery_service = get_mastery_service()

        for response in responses:
            mastery_service.update_mastery(
                user=request.user,
                topic_id=str(response.question.quiz.topic_id),
                is_correct=response.is_correct,
            )

        # Log quiz completion event
        activity_service = get_activity_service()
        activity_service.log_quiz_completed(
            user=request.user,
            quiz_id=str(attempt.quiz.id),
            attempt_id=str(attempt.id),
            score=score,
        )

    logger.info(
        "quiz_submitted",
        attempt_id=str(attempt.id),
        score=score,
        correct=correct_count,
        total=total_questions,
    )

    # Return results with questions and explanations
    result_data = QuizAttemptSerializer(attempt).data

    # Add questions with answers for review
    questions_with_answers = QuestionDetailSerializer(questions, many=True).data
    result_data["questions_with_answers"] = questions_with_answers

    return Response(result_data)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_attempt_result(request: Request, attempt_id: str) -> Response:
    """
    Get quiz attempt results.

    GET /api/v1/assessment/attempts/{attempt_id}/

    Returns:
        200: Attempt results with explanations
        404: Attempt not found
        403: Not authorized to view
    """
    attempt = get_object_or_404(
        QuizAttempt.objects.prefetch_related(
            "responses__question", "quiz__questions"
        ).select_related("quiz__topic"),
        id=attempt_id,
    )

    # Check authorization (for authenticated users)
    if request.user.is_authenticated and attempt.user and attempt.user != request.user:
        return Response(
            {"error": "FORBIDDEN", "message": "You cannot view this attempt"},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = QuizAttemptSerializer(attempt)
    result_data = serializer.data

    # Add questions with answers if submitted
    if attempt.status == "submitted":
        questions_with_answers = QuestionDetailSerializer(
            attempt.quiz.questions.all(), many=True
        ).data
        result_data["questions_with_answers"] = questions_with_answers

    return Response(result_data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_user_attempts(request: Request) -> Response:
    """
    List user's quiz attempts.

    GET /api/v1/assessment/my-attempts/
    Query params:
        - quiz_id: UUID (optional)
        - status: active|submitted|abandoned (optional)

    Returns:
        200: List of attempts
    """
    user = cast(User, request.user)
    queryset = QuizAttempt.objects.filter(user=user)

    # Apply filters
    quiz_id = request.query_params.get("quiz_id")
    if quiz_id:
        queryset = queryset.filter(quiz_id=quiz_id)

    status_filter = request.query_params.get("status")
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    attempts = queryset.select_related("quiz__topic").order_by("-started_at")

    paginator = StandardPageNumberPagination()
    paginated_attempts = paginator.paginate_queryset(attempts, request)
    serializer = QuizAttemptSerializer(paginated_attempts, many=True)

    return paginator.get_paginated_response(serializer.data)
