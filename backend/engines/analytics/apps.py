"""
Analytics Engine App Configuration
"""

from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    """Analytics Engine configuration."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'engines.analytics'
    verbose_name = 'Analytics Engine'
    