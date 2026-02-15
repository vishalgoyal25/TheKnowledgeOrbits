"""
Auth Engine App Configuration
"""

from django.apps import AppConfig


class AuthConfig(AppConfig):
    """Auth Engine configuration."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'engines.auth'
    label = 'authentication'
    verbose_name = 'Auth Engine'