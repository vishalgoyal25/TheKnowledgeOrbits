from django.apps import AppConfig


class TagsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "engines.tags"
    label = "tags"
    verbose_name = "Tags & Concepts"
