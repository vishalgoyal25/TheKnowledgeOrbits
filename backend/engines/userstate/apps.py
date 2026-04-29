from django.apps import AppConfig


class UserstateConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "engines.userstate"
    label = "userstate"
    verbose_name = "User State"

    def ready(self) -> None:
        from engines.userstate.signals import _register  # noqa: PLC0415

        _register()
