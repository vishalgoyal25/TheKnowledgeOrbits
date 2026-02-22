"""
Content Engine App Configuration
"""

from django.apps import AppConfig


class ContentConfig(AppConfig):
    """
    Configuration for the Content Engine.

    Responsible for content ingestion, chunking, and embedding generation.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "engines.content"
    verbose_name = "Content Engine"

    def ready(self):
        """
        Import signal handlers and perform startup tasks.
        """
        # Import signals when ready (will be added in future phases)
        # import engines.content.signals
        pass
