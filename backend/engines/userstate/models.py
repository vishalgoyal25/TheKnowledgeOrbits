"""
User State Engine Models (PKB-Compliant)

Tables (per DATABASE_SCHEMA.md):
- userstate_event
- userstate_progress
- userstate_topic_mastery
- userstate_bookmark
- userstate_reading_progress
"""

import uuid
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class UserEvent(models.Model):
    """
    User event log (event sourcing).

    Schema from DATABASE_SCHEMA.md (lines 221-227):
    - id (UUID)
    - user_id (FK to auth_user)
    - event_type (article_read, quiz_started, quiz_completed)
    - event_data (JSONB)
    - created_at
    """

    EVENT_TYPE_CHOICES = [
        ("article_read", "Article Read"),
        ("article_generated", "Article Generated"),
        ("quiz_started", "Quiz Started"),
        ("quiz_completed", "Quiz Completed"),
        ("bookmark_added", "Bookmark Added"),
        ("bookmark_removed", "Bookmark Removed"),
        ("login", "Login"),
        ("logout", "Logout"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="events",
        help_text="User who performed action",
    )

    event_type = models.CharField(
        max_length=50, choices=EVENT_TYPE_CHOICES, help_text="Type of event"
    )

    event_data = models.JSONField(default=dict, help_text="Additional event metadata")

    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Event timestamp", db_index=True
    )

    class Meta:
        db_table = "userstate_event"  # PKB requirement
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["event_type"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} - {self.event_type}"


class UserProgress(models.Model):
    """
    User progress aggregation.

    Schema from DATABASE_SCHEMA.md (lines 229-237):
    - id (UUID)
    - user_id (FK to auth_user, UNIQUE)
    - total_articles_read
    - total_quizzes_taken
    - current_streak
    - syllabus_coverage_percent
    - updated_at
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="progress",
        help_text="User",
    )

    total_articles_read = models.IntegerField(
        default=0, help_text="Total articles read"
    )

    total_quizzes_taken = models.IntegerField(
        default=0, help_text="Total quizzes taken"
    )

    current_streak = models.IntegerField(
        default=0, help_text="Current consecutive days active"
    )

    syllabus_coverage_percent = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Percentage of syllabus covered",
    )

    updated_at = models.DateTimeField(auto_now=True, help_text="Last update timestamp")

    class Meta:
        db_table = "userstate_progress"  # PKB requirement
        ordering = ["user"]

    def __str__(self) -> str:
        return f"{self.user.email} - Progress"


class TopicMastery(models.Model):
    """
    User topic mastery scores.

    Schema from DATABASE_SCHEMA.md (lines 239-248):
    - id (UUID)
    - user_id (FK to auth_user)
    - topic_id (FK to knowledge_topic)
    - mastery_score (0-100)
    - questions_attempted
    - questions_correct
    - updated_at
    - UNIQUE(user_id, topic_id)
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="topic_masteries",
        help_text="User",
    )

    topic = models.ForeignKey(
        "knowledge.Topic",
        on_delete=models.CASCADE,
        related_name="user_masteries",
        help_text="Topic",
    )

    mastery_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Mastery percentage (0-100)",
    )

    questions_attempted = models.IntegerField(
        default=0, help_text="Total questions attempted for this topic"
    )

    questions_correct = models.IntegerField(
        default=0, help_text="Total questions answered correctly"
    )

    updated_at = models.DateTimeField(auto_now=True, help_text="Last update timestamp")

    class Meta:
        db_table = "userstate_topic_mastery"  # PKB requirement
        unique_together = [["user", "topic"]]
        ordering = ["-mastery_score"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["topic"]),
            models.Index(fields=["user", "-mastery_score"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} - {self.topic.name}: {self.mastery_score:.1f}%"

    def update_mastery(self):
        """Recalculate mastery score."""
        if self.questions_attempted > 0:
            self.mastery_score = (
                self.questions_correct / self.questions_attempted
            ) * 100
            self.save()


class Bookmark(models.Model):
    """
    User bookmarks.

    Schema from DATABASE_SCHEMA.md (lines 250-257):
    - id (UUID)
    - user_id (FK to auth_user)
    - content_type ('article', 'quiz', 'chunk')
    - content_id (UUID)
    - created_at
    - UNIQUE(user_id, content_type, content_id)
    """

    CONTENT_TYPE_CHOICES = [
        ("article", "Article"),
        ("quiz", "Quiz"),
        ("chunk", "Chunk"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookmarks",
        help_text="User who bookmarked",
    )

    content_type = models.CharField(
        max_length=50,
        choices=CONTENT_TYPE_CHOICES,
        help_text="Type of content bookmarked",
    )

    content_id = models.UUIDField(help_text="UUID of bookmarked content")

    notes = models.TextField(blank=True, help_text="Personal notes (extension to PKB)")

    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Bookmark creation timestamp"
    )

    class Meta:
        db_table = "userstate_bookmark"  # PKB requirement
        unique_together = [["user", "content_type", "content_id"]]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["content_type"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} - {self.content_type}: {self.content_id}"


class ReadingProgress(models.Model):
    """
    Article reading progress.

    Schema from DATABASE_SCHEMA.md (lines 259-267):
    - id (UUID)
    - user_id (FK to auth_user)
    - article_id (UUID)
    - percent_read (0.0-100.0)
    - last_position (integer)
    - updated_at
    - UNIQUE(user_id, article_id)
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reading_progress",
        help_text="User",
    )

    article_id = models.UUIDField(
        help_text="Article UUID (from article_generation engine)"
    )

    percent_read = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Percentage of article read",
    )

    last_position = models.IntegerField(
        default=0, help_text="Last scroll position or paragraph index"
    )

    updated_at = models.DateTimeField(auto_now=True, help_text="Last update timestamp")

    class Meta:
        db_table = "userstate_reading_progress"  # PKB requirement
        unique_together = [["user", "article_id"]]
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["article_id"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.user.email} - Article {self.article_id}: {self.percent_read:.1f}%"
        )
