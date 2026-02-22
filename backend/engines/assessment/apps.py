"""
Assessment Engine App Configuration
"""

from typing import Any

from django.apps import AppConfig


class AssessmentConfig(AppConfig):
    """Configuration for Assessment Engine."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "engines.assessment"
    verbose_name = "Assessment Engine"

    def ready(self) -> Any:
        """Import signals when app is ready."""
        # Import signals here if needed in future
