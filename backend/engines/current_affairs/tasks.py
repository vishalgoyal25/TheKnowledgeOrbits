from background_task import background
from django.utils import timezone
import structlog
from .services.rss_scraper import RSSScraperService
from .services.ca_processor import CAProcessorService
from .services.topic_linker import TopicLinkerService

logger = structlog.get_logger(__name__)


@background(schedule=60)
def auto_scrape_and_process_ca():
    """
    Automated task to scrape, process, and link Current Affairs.
    Designed to run periodically without manual intervention.
    """
    logger.info("automated_ca_sync_started")

    try:
        # 1. Scrape
        scrape_result = RSSScraperService.scrape_all_active()
        logger.info(
            "automated_scrape_complete",
            new_articles=scrape_result.get("articles_new", 0),
        )

        # 2. Process (Full Batch)
        processed_total = 0
        while True:
            count = CAProcessorService.process_pending_articles(batch_size=50)
            if count == 0:
                break
            processed_total += count
        logger.info("automated_processing_complete", total=processed_total)

        # 3. Link
        linked_count = TopicLinkerService.link_unlinked_chunks(batch_size=100)
        logger.info("automated_linking_complete", total=linked_count)

        logger.info("automated_ca_sync_success", timestamp=timezone.now())

    except Exception as e:
        logger.error("automated_ca_sync_failed", error=str(e))
        raise e
