"""
Assessment Engine Admin Interface
"""

from django.contrib import admin
from django.utils.html import format_html

from engines.assessment.models import Quiz, Question, QuizAttempt, QuestionResponse


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    """Admin interface for Quiz model."""

    list_display = [
        "title",
        "topic",
        "difficulty_level",
        "include_ca",
        "question_count",
        "is_active",
        "created_at",
    ]
    list_filter = ["difficulty_level", "include_ca", "is_active", "created_at"]
    search_fields = ["title", "topic__name"]
    readonly_fields = ["created_at", "updated_at", "generation_metadata"]

    fieldsets = (
        ("Basic Info", {"fields": ("title", "topic", "difficulty_level")}),
        (
            "Configuration",
            {"fields": ("include_ca", "question_count", "time_limit", "is_active")},
        ),
        (
            "Metadata",
            {
                "fields": ("generation_metadata", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """Admin interface for Question model."""

    list_display = [
        "quiz_title",
        "order_index",
        "question_type",
        "difficulty_level",
        "correct_answer",
        "has_sources",
    ]
    list_filter = ["question_type", "difficulty_level", "quiz"]
    search_fields = ["question_text", "quiz__title"]
    readonly_fields = ["created_at"]

    fieldsets = (
        (
            "Question",
            {"fields": ("quiz", "order_index", "question_text", "question_type")},
        ),
        ("Multi-Statement", {"fields": ("statements",), "classes": ("collapse",)}),
        ("Options & Answer", {"fields": ("options", "correct_answer", "explanation")}),
        ("Metadata", {"fields": ("difficulty_level", "created_at")}),
        (
            "Sources",
            {
                "fields": ("source_static_chunks", "source_ca_chunks"),
                "classes": ("collapse",),
            },
        ),
    )

    filter_horizontal = ["source_static_chunks", "source_ca_chunks"]

    def quiz_title(self, obj):
        return obj.quiz.title

    quiz_title.short_description = "Quiz"

    def has_sources(self, obj):
        static = obj.source_static_chunks.count()
        ca = obj.source_ca_chunks.count()
        return format_html(
            '<span style="color: blue;">Static: {}</span> | '
            '<span style="color: green;">CA: {}</span>',
            static,
            ca,
        )

    has_sources.short_description = "Sources"


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    """Admin interface for QuizAttempt model."""

    list_display = [
        "user_display",
        "quiz",
        "status",
        "score_display",
        "correct_count",
        "started_at",
        "time_spent_display",
    ]
    list_filter = ["status", "started_at"]
    search_fields = ["user__username", "quiz__title"]
    readonly_fields = ["started_at", "submitted_at", "attempt_metadata"]

    fieldsets = (
        ("Attempt Info", {"fields": ("quiz", "user", "status")}),
        (
            "Results",
            {"fields": ("score", "correct_count", "wrong_count", "unanswered_count")},
        ),
        ("Timing", {"fields": ("started_at", "submitted_at", "time_spent")}),
        ("Metadata", {"fields": ("attempt_metadata",), "classes": ("collapse",)}),
    )

    def user_display(self, obj):
        return obj.user.username if obj.user else "Guest"

    user_display.short_description = "User"

    def score_display(self, obj):
        if obj.score is not None:
            color = (
                "green" if obj.score >= 70 else "orange" if obj.score >= 50 else "red"
            )
            return format_html(
                '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
                color,
                obj.score,
            )
        return "-"

    score_display.short_description = "Score"

    def time_spent_display(self, obj):
        if obj.time_spent:
            minutes = obj.time_spent // 60
            seconds = obj.time_spent % 60
            return f"{minutes}m {seconds}s"
        return "-"

    time_spent_display.short_description = "Time"


@admin.register(QuestionResponse)
class QuestionResponseAdmin(admin.ModelAdmin):
    """Admin interface for QuestionResponse model."""

    list_display = [
        "attempt_user",
        "question_text_short",
        "selected_option",
        "is_correct_display",
        "time_spent",
    ]
    list_filter = ["is_correct", "marked_for_review"]
    search_fields = ["attempt__user__username", "question__question_text"]
    readonly_fields = ["created_at", "first_visited_at", "answered_at"]

    def attempt_user(self, obj):
        return obj.attempt.user.username if obj.attempt.user else "Guest"

    attempt_user.short_description = "User"

    def question_text_short(self, obj):
        return obj.question.question_text[:60] + "..."

    question_text_short.short_description = "Question"

    def is_correct_display(self, obj):
        if not obj.selected_option:
            return format_html('<span style="color: gray;">○ Unanswered</span>')
        elif obj.is_correct:
            return format_html('<span style="color: green;">✓ Correct</span>')
        else:
            return format_html('<span style="color: red;">✗ Wrong</span>')

    is_correct_display.short_description = "Result"
