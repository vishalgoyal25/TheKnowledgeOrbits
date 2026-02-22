from django.apps import AppConfig


class SupportConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "engines.support"
    label = "support_engine"
    verbose_name = "Support & Feedback"
