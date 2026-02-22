"""
Assessment Engine App Configuration
"""

from django.apps import AppConfig


class AssessmentConfig(AppConfig):
    """Configuration for Assessment Engine."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "engines.assessment"
    verbose_name = "Assessment Engine"

    def ready(self):
        """Import signals when app is ready."""
        # Import signals here if needed in future
        pass
