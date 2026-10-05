from typing import Any

from django.apps import AppConfig


class DataFactoryConfig(AppConfig):
    """App config for the Data Factory engine.

    ``label`` is what Django uses for the migration namespace and for
    ``app_label.ModelName`` lookups. Table names are set explicitly via
    ``db_table`` on every model, so the ``df_`` prefix never depends on this.
    """

    # Fallback PK type for a model that declares no primary key. It should
    # never be exercised here: CLAUDE.md 4.2 requires an explicit UUID primary
    # key on every model, and every model in this engine declares one. Set only
    # to silence Django's W042 system check, and matched to the value the older
    # engines use so the project stays uniform.
    default_auto_field = "django.db.models.BigAutoField"

    name = "engines.data_factory"
    label = "data_factory"
    verbose_name = "Data Factory"

    def ready(self) -> Any:
        """Startup hook. Nothing to register in phase 0.1.

        Two things MUST be imported here when they arrive, or they fail
        silently rather than loudly:

        1. ``@background`` tasks -- django-background-tasks only knows about
           tasks that were imported during startup. Enqueueing an unimported
           task succeeds and then never runs (CLAUDE.md 4.4). Restart
           ``process_tasks`` after adding one.
        2. Signal receivers -- see ``engines/userstate/signals.py`` for the
           ``_register()`` pattern this project uses.

        Import INSIDE this method, never at module scope: ``apps.py`` is
        evaluated during app loading, which runs ahead of the URL system check,
        so a module-level import of anything that reaches an LLM SDK would
        break every ``manage.py`` command and the GitHub Actions scraper
        (CLAUDE.md 4.1).
        """
        return None
