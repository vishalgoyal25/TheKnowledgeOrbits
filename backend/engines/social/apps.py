"""
engines/social/apps.py
━━━━━━━━━━━━━━━━━━━━━━
Social Interaction Engine — AppConfig.

Registers the social engine with Django and wires up post_save / post_delete
signals (SocialCount cache + UserEvent fire-and-forget) on app ready.
"""

from django.apps import AppConfig


class SocialConfig(AppConfig):
    name = "engines.social"
    label = "social"
    default_auto_field = "django.db.models.BigAutoField"
    verbose_name = "Social Interactions"

    def ready(self) -> None:
        import engines.social.signals  # noqa: F401 — registers all signal handlers
