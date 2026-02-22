"""
Assessment Engine Serializers

DRF serializers for API endpoints.
"""

from rest_framework import serializers

from engines.assessment.models import Quiz, Question, QuizAttempt, QuestionResponse
from engines.knowledge.models import Topic


class TopicMinimalSerializer(serializers.ModelSerializer):
    """Minimal topic serializer for nested use."""

    class Meta:
        model = Topic
        fields = ["id", "name", "difficulty_level"]


class QuestionListSerializer(serializers.ModelSerializer):
    """
    Serializer for Question in quiz listing (WITHOUT correct answer).
    Used when quiz is being taken.
    """

    class Meta:
        model = Question
        fields = [
            "id",
            "question_text",
            "question_type",
            "statements",
            "options",
            "difficulty_level",
            "order_index",
        ]
        # Explicitly exclude correct_answer and explanation


class QuestionDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for Question with correct answer and explanation.
    Used after quiz submission for review.
    """

    has_static_sources = serializers.BooleanField(read_only=True)
    has_ca_sources = serializers.BooleanField(read_only=True)

    class Meta:
        model = Question
        fields = [
            "id",
            "question_text",
            "question_type",
            "statements",
            "options",
            "correct_answer",
            "explanation",
            "difficulty_level",
            "order_index",
            "has_static_sources",
            "has_ca_sources",
        ]


class QuizListSerializer(serializers.ModelSerializer):
    """Serializer for Quiz listing."""

    topic = TopicMinimalSerializer(read_only=True)
    created_by_email = serializers.EmailField(
        source="created_by.email", read_only=True, allow_null=True
    )
    is_user_owned = serializers.BooleanField(read_only=True)

    class Meta:
        model = Quiz
        fields = [
            "id",
            "title",
            "topic",
            "difficulty_level",
            "include_ca",
            "question_count",
            "time_limit",
            "is_active",
            "created_by",
            "created_by_email",
            "is_public",
            "is_user_owned",
            "created_at",
        ]


class QuizDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for Quiz detail (includes questions WITHOUT answers).
    Used when starting a quiz.
    """

    topic = TopicMinimalSerializer(read_only=True)
    questions = QuestionListSerializer(many=True, read_only=True)
    created_by_email = serializers.EmailField(
        source="created_by.email", read_only=True, allow_null=True
    )
    is_user_owned = serializers.BooleanField(read_only=True)

    class Meta:
        model = Quiz
        fields = [
            "id",
            "title",
            "topic",
            "difficulty_level",
            "include_ca",
            "question_count",
            "time_limit",
            "questions",
            "created_by",
            "created_by_email",
            "is_public",
            "is_user_owned",
            "created_at",
        ]


class QuizGenerateSerializer(serializers.Serializer):
    """Serializer for quiz generation request."""

    topic_id = serializers.UUIDField(required=True)
    difficulty = serializers.ChoiceField(
        choices=["easy", "medium", "hard"], default="medium"
    )
    include_ca = serializers.BooleanField(default=False)
    question_count = serializers.IntegerField(min_value=5, max_value=20, default=10)


class QuestionResponseSerializer(serializers.ModelSerializer):
    """Serializer for question response."""

    question_detail = QuestionDetailSerializer(source="question", read_only=True)

    class Meta:
        model = QuestionResponse
        fields = [
            "id",
            "question",
            "question_detail",
            "selected_option",
            "is_correct",
            "time_spent",
            "marked_for_review",
            "answered_at",
        ]
        read_only_fields = ["is_correct", "answered_at"]


class QuizAttemptSerializer(serializers.ModelSerializer):
    """Serializer for quiz attempt."""

    quiz = QuizListSerializer(read_only=True)
    responses = QuestionResponseSerializer(many=True, read_only=True)
    accuracy = serializers.FloatField(read_only=True)

    class Meta:
        model = QuizAttempt
        fields = [
            "id",
            "quiz",
            "user",
            "status",
            "score",
            "accuracy",
            "correct_count",
            "wrong_count",
            "unanswered_count",
            "started_at",
            "submitted_at",
            "time_spent",
            "responses",
        ]
        read_only_fields = [
            "score",
            "correct_count",
            "wrong_count",
            "unanswered_count",
            "started_at",
            "accuracy",
        ]


class QuizSubmitSerializer(serializers.Serializer):
    """Serializer for quiz submission."""

    attempt_id = serializers.UUIDField(required=True)
    answers = serializers.ListField(child=serializers.DictField(), required=True)

    def validate_answers(self, value):
        """Validate answers format."""
        for answer in value:
            if "question_id" not in answer:
                raise serializers.ValidationError("Each answer must have 'question_id'")
            if "selected_option" not in answer:
                raise serializers.ValidationError(
                    "Each answer must have 'selected_option'"
                )
        return value
