from django.apps import AppConfig


class DailyCaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "engines.daily_ca"
    label = "daily_ca"
    verbose_name = "Daily CA"

    def ready(self):
        # Register post_save signal — auto-generates semantic embeddings
        # when a DailyCaArticle is published (admin or cron auto-publish).
        import engines.daily_ca.signals  # noqa: F401
