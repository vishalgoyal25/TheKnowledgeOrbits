"""
Authorization Engine App Configuration
"""

from django.apps import AppConfig


class AuthorizationConfig(AppConfig):
    """Authorization Engine configuration."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "engines.authorization"
    verbose_name = "Authorization Engine"
