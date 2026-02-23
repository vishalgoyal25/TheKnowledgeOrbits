"""
Article Generation Engine App Configuration
"""

from typing import Any

from django.apps import AppConfig

import structlog

logger = structlog.get_logger(__name__)


class ArticleGenerationConfig(AppConfig):
    """Configuration for Article Generation Engine."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "engines.article_generation"
    verbose_name = "Article Generation Engine"

    def ready(self) -> Any:
        """Initialize engine on startup."""
        logger.info("article_generation_engine_initialized")
