"""
Telemetry Engine App Configuration
"""

from django.apps import AppConfig


class TelemetryConfig(AppConfig):
    """
    Telemetry Engine configuration.

    No ready() hook is needed: this engine registers no signals and no
    @background tasks. Telemetry writes go straight to the database — routing
    them through django-background-tasks would persist each write AS a task
    row, costing an insert plus a delete instead of a single insert.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "engines.telemetry"
    verbose_name = "Telemetry Engine"
