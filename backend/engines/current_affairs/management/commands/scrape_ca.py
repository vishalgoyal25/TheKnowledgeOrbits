"""
Management command to scrape CA sources

Usage:
    python manage.py scrape_ca
"""

from typing import Any

from django.core.management.base import BaseCommand

from engines.current_affairs.services.ca_processor import CAProcessorService
from engines.current_affairs.services.rss_scraper import RSSScraperService
from engines.current_affairs.services.topic_linker import TopicLinkerService


class Command(BaseCommand):
    help = "Scrape current affairs from RSS feeds, process, and link to topics"

    def add_arguments(self, parser) -> Any:  # type: ignore
        parser.add_argument(
            "--scrape-only",
            action="store_true",
            help="Only scrape, do not process or link",
        )
        parser.add_argument(
            "--process-only",
            action="store_true",
            help="Only process pending articles",
        )
        parser.add_argument(
            "--link-only",
            action="store_true",
            help="Only link unlinked chunks",
        )

    def handle(self, *args, **options) -> Any:  # type: ignore
        scrape_only = options["scrape_only"]
        process_only = options["process_only"]
        link_only = options["link_only"]

        # If no specific flag, do all
        do_all = not (scrape_only or process_only or link_only)

        # Scrape
        if do_all or scrape_only:
            self.stdout.write("Scraping RSS feeds...")
            result = RSSScraperService.scrape_all_active()

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Scraped {result['sources_scraped']} sources: "
                    f"{result['articles_new']} new articles"
                )
            )

            if result["sources_failed"] > 0:
                self.stdout.write(
                    self.style.WARNING(f"  {result['sources_failed']} sources failed")
                )

        if do_all or process_only:
            self.stdout.write("Processing pending articles...")

            total_processed = 0
            while True:
                processed = CAProcessorService.process_pending_articles(batch_size=50)
                if processed == 0:
                    break
                total_processed += processed
                self.stdout.write(f"  Processed batch of {processed} articles...")

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Processed total {total_processed} articles into chunks"
                )
            )

        # Link
        if do_all or link_only:
            self.stdout.write("Linking chunks to topics...")
            # Note: We now properly return the number of LINKS created as per recent update
            linked_count = TopicLinkerService.link_unlinked_chunks(batch_size=100)

            self.stdout.write(
                self.style.SUCCESS(f"✓ Linked {linked_count} chunks to topics")
            )

        self.stdout.write(self.style.SUCCESS("\n✓ Current affairs update complete!"))
