"""
Knowledge Engine Django App Configuration
"""
from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    """Configuration for Knowledge Engine."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'engines.knowledge'
    verbose_name = 'Knowledge Engine'
    
    def ready(self):
        """Initialize engine when Django starts."""
        import structlog
        logger = structlog.get_logger(__name__)
        logger.info("knowledge_engine_initialized")
        