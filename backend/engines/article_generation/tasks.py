from django.utils import timezone

import sentry_sdk
import structlog
from background_task import background

from .models import Article, ArticleGenerationJob
from .services.generation_service import ArticleGenerationService

logger = structlog.get_logger(__name__)


@background(schedule=0)
def generate_article_task(
    job_id: str, topic_id: str, include_ca: bool, user_id: int = None
):
    """
    Background task to generate an article using RAG.
    Updates the ArticleGenerationJob status.
    """
    job = ArticleGenerationJob.objects.get(id=job_id)
    job.status = "processing"
    job.started_at = timezone.now()
    job.save()

    logger.info(
        "background_article_generation_started", job_id=job_id, topic_id=topic_id
    )

    try:
        # Perform generation
        result = ArticleGenerationService.generate_article(
            topic_id=topic_id, include_ca=include_ca, user_id=user_id
        )

        # Update article metadata (ownership handled in service or post-generation)
        article = Article.objects.get(id=result["article_id"])

        # Link job to article
        job.article = article
        job.status = "completed"
        job.completed_at = timezone.now()
        job.save()

        logger.info(
            "background_article_generation_success",
            job_id=job_id,
            article_id=str(article.id),
        )

    except Exception as e:
        sentry_sdk.capture_exception(e)
        job.status = "failed"
        job.error_log = str(e)
        job.save()
        logger.error(
            "background_article_generation_failed", job_id=job_id, error=str(e)
        )
