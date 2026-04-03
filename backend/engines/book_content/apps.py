from django.apps import AppConfig


class BookContentConfig(AppConfig):
    """Book Content Engine — static UPSC syllabus generation."""

    default_auto_field = "django.db.models.UUIDField"
    name = "engines.book_content"
    label = "book_content"
