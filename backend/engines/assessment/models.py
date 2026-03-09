"""
Assessment Engine Models

Core Models:
- Quiz: Container for questions (linked to Topic, difficulty, include_ca flag)
- Question: Individual MCQ (supports multi-statement, assertion-reasoning)
- QuizAttempt: User's quiz session (score, timing, status)
- QuestionResponse: Granular answer tracking per question

Design Principles:
- UUID primary keys (no auto-increment)
- Source attribution via M2M to Chunk and CAChunk
- Nullable user field (guest mode support)
- Comprehensive indexing for performance
"""

import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Quiz(models.Model):
    """
    Quiz container model.

    Each quiz is generated for a specific topic with configurable parameters.
    The include_ca flag determines whether current affairs are mixed with static content.
    """

    DIFFICULTY_CHOICES = [
        ("easy", "Easy"),
        ("medium", "Medium"),
        ("hard", "Hard"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )

    title = models.CharField(
        max_length=500,
        help_text="Quiz title (e.g., 'UPSC Polity: Fundamental Rights Quiz')",
    )

    topic = models.ForeignKey(
        "knowledge.Topic",
        on_delete=models.CASCADE,
        related_name="quizzes",
        help_text="Target topic for this quiz",
    )

    difficulty_level = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default="medium",
        help_text="Overall quiz difficulty",
    )

    include_ca = models.BooleanField(
        default=False, help_text="Whether to include Current Affairs (Hybrid Mode)"
    )

    question_count = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(50)],
        help_text="Number of questions in quiz",
    )

    time_limit = models.IntegerField(
        null=True, blank=True, help_text="Time limit in seconds (null = no limit)"
    )

    is_active = models.BooleanField(
        default=True, help_text="Is quiz available for attempts?"
    )

    # Generation metadata
    generation_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Groq params, chunk IDs used, generation timestamp, etc.",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Quiz creation timestamp"
    )

    updated_at = models.DateTimeField(
        auto_now=True, help_text="Last modification timestamp"
    )

    # ===== OWNERSHIP FIELDS (PKB EXTENSION) =====
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_quizzes",
        null=True,
        blank=True,
        help_text="User who created this quiz (NULL = system/admin)",
    )

    is_public = models.BooleanField(
        default=True, help_text="Is quiz publicly accessible?"
    )
    # ===== END OWNERSHIP FIELDS =====

    class Meta:
        db_table = "assessment_quiz"
        ordering = ["-created_at"]
        verbose_name_plural = "Quizzes"
        indexes = [
            models.Index(fields=["topic", "-created_at"]),
            models.Index(fields=["created_by", "-created_at"]),
            models.Index(fields=["difficulty_level"]),
            models.Index(fields=["include_ca"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        ca_marker = " [CA]" if self.include_ca else ""
        return f"{self.title}{ca_marker} ({self.difficulty_level})"

    @property
    def is_user_owned(self) -> bool:
        """Check if quiz is user-owned."""
        return self.created_by is not None


class Question(models.Model):
    """
    Individual question model.

    Supports multiple question types:
    - single_mcq: Simple single-answer MCQ
    - multi_statement: UPSC-style "Which of the following is/are correct?"
    - assertion_reasoning: Statement + Reason with logical connection testing
    """

    QUESTION_TYPE_CHOICES = [
        ("single_mcq", "Single MCQ"),
        ("multi_statement", "Multi-Statement"),
        ("assertion_reasoning", "Assertion-Reasoning"),
    ]

    DIFFICULTY_CHOICES = [
        ("easy", "Easy"),
        ("medium", "Medium"),
        ("hard", "Hard"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="questions",
        help_text="Parent quiz",
    )

    question_text = models.TextField(help_text="The question stem/text")

    question_type = models.CharField(
        max_length=30,
        choices=QUESTION_TYPE_CHOICES,
        default="single_mcq",
        help_text="Question format type",
    )

    statements = models.JSONField(
        default=list,
        blank=True,
        help_text="Array of statements for multi-statement questions",
    )

    options = models.JSONField(
        help_text="Answer options as JSON object {A: 'text', B: 'text', C: 'text', D: 'text'}"
    )

    correct_answer = models.CharField(
        max_length=10, help_text="Correct option key (A, B, C, or D)"
    )

    explanation = models.TextField(
        help_text="Detailed explanation with source citations"
    )

    difficulty_level = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default="medium",
        help_text="Question difficulty",
    )

    # Source attribution (Many-to-Many)
    source_static_chunks = models.ManyToManyField(
        "content.Chunk",
        related_name="questions_generated",
        blank=True,
        help_text="Static chunks used to generate this question",
    )

    source_ca_chunks = models.ManyToManyField(
        "current_affairs.CAChunk",
        related_name="questions_generated",
        blank=True,
        help_text="CA chunks used to generate this question",
    )

    order_index = models.IntegerField(default=0, help_text="Display order within quiz")

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Question creation timestamp"
    )

    class Meta:
        db_table = "assessment_question"
        ordering = ["quiz", "order_index"]
        indexes = [
            models.Index(fields=["quiz", "order_index"]),
            models.Index(fields=["question_type"]),
            models.Index(fields=["difficulty_level"]),
        ]

    def __str__(self) -> str:
        return f"Q{self.order_index + 1}: {self.question_text[:60]}..."

    @property
    def has_static_sources(self) -> bool:
        """Check if question uses static chunks."""
        return self.source_static_chunks.exists()

    @property
    def has_ca_sources(self) -> bool:
        """Check if question uses CA chunks."""
        return self.source_ca_chunks.exists()


class QuizAttempt(models.Model):
    """
    User's quiz attempt/session model.

    Tracks entire quiz-taking session including timing, score, and completion status.
    User field is nullable to support guest mode.
    """

    STATUS_CHOICES = [
        ("active", "Active"),
        ("submitted", "Submitted"),
        ("abandoned", "Abandoned"),
        ("expired", "Expired"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="attempts",
        help_text="Quiz being attempted",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quiz_attempts",
        null=True,
        blank=True,
        help_text="User taking quiz (null for guest mode)",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        help_text="Current attempt status",
    )

    score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Score percentage (0-100)",
    )

    correct_count = models.IntegerField(
        default=0, help_text="Number of correct answers"
    )

    wrong_count = models.IntegerField(default=0, help_text="Number of wrong answers")

    unanswered_count = models.IntegerField(
        default=0, help_text="Number of unanswered questions"
    )

    # Timing
    started_at = models.DateTimeField(
        auto_now_add=True, help_text="When quiz was started"
    )

    submitted_at = models.DateTimeField(
        null=True, blank=True, help_text="When quiz was submitted"
    )

    time_spent = models.IntegerField(
        null=True, blank=True, help_text="Total time spent in seconds"
    )

    # Metadata
    attempt_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Browser info, IP (for analytics), question order seen, etc.",
    )

    class Meta:
        db_table = "assessment_quiz_attempt"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["quiz"]),
            models.Index(fields=["user"]),
            models.Index(fields=["status"]),
            models.Index(fields=["-started_at"]),
            models.Index(fields=["quiz", "user"]),
            models.Index(fields=["user", "-started_at"]),
            models.Index(fields=["quiz", "-started_at"]),
        ]

    def __str__(self) -> str:
        user_info = self.user.email if self.user else "Guest"
        return f"{user_info} - {self.quiz.title} ({self.status})"

    @property
    def accuracy(self) -> float:
        """Calculate accuracy percentage."""
        total = self.correct_count + self.wrong_count
        if total == 0:
            return 0.0
        return (self.correct_count / total) * 100


class QuestionResponse(models.Model):
    """
    Individual question response model.

    Tracks user's answer to each question with granular timing data.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )

    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name="responses",
        help_text="Parent quiz attempt",
    )

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="responses",
        help_text="Question being answered",
    )

    selected_option = models.CharField(
        max_length=10,
        blank=True,
        help_text="User's selected answer (A, B, C, D, or empty if unanswered)",
    )

    is_correct = models.BooleanField(
        default=False, help_text="Whether answer is correct"
    )

    time_spent = models.IntegerField(
        default=0, help_text="Time spent on this question in seconds"
    )

    marked_for_review = models.BooleanField(
        default=False, help_text="Whether user marked this for review"
    )

    # Timestamps
    first_visited_at = models.DateTimeField(
        null=True, blank=True, help_text="When user first viewed this question"
    )

    answered_at = models.DateTimeField(
        null=True, blank=True, help_text="When user answered this question"
    )

    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Response record creation timestamp"
    )

    class Meta:
        db_table = "assessment_question_response"
        unique_together = [["attempt", "question"]]
        ordering = ["attempt", "question__order_index"]
        indexes = [
            models.Index(fields=["attempt"]),
            models.Index(fields=["question"]),
            models.Index(fields=["is_correct"]),
        ]

    def __str__(self) -> str:
        status = "✓" if self.is_correct else "✗" if self.selected_option else "○"
        return f"{status} Q{self.question.order_index + 1} - {self.selected_option or 'Unanswered'}"
