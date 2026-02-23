import sentry_sdk

"""
RSS Scraper Service

Scrapes RSS feeds from news sources
"""

from datetime import datetime
from typing import Any, Dict

from django.db import transaction
from django.utils import timezone

import feedparser
import requests
import structlog
from bs4 import BeautifulSoup

from ..models import CAArticle, CASource

logger = structlog.get_logger(__name__)


class RSSScraperService:
    """RSS feed scraping service"""

    @staticmethod
    def scrape_source(source: CASource) -> Dict[str, Any]:
        """
        Scrape a single source
        """
        logger.info("scraping_source", source_name=source.name)

        try:
            # Parse RSS feed
            feed = feedparser.parse(source.url)
            if feed.bozo:
                error_msg = f"Feed parsing error: {feed.bozo_exception}"
                logger.error(
                    "feed_parsing_error", error=error_msg, source_name=source.name
                )

                source.last_error = error_msg
                source.save()

                return {
                    "success": False,
                    "articles_found": 0,
                    "articles_new": 0,
                    "error": error_msg,
                }

            # Process entries
            articles_found = len(feed.entries)
            articles_new = 0

            for entry in feed.entries:
                try:
                    article_created = RSSScraperService._process_entry(source, entry)
                    if article_created:
                        articles_new += 1
                except Exception as e:
                    sentry_sdk.capture_exception(e)
                    logger.warning(f"Failed to process entry: {e}")

            # Update source stats
            source.last_scraped_at = timezone.now()
            source.last_error = ""
            source.article_count = CAArticle.objects.filter(
                source=source
            ).count()  # Sync count from DB
            source.save()

            logger.info(
                f"Scraping complete: {articles_new}/{articles_found} new articles"
            )

            return {
                "success": True,
                "articles_found": articles_found,
                "articles_new": articles_new,
                "error": None,
            }

        except Exception as e:
            sentry_sdk.capture_exception(e)
            error_msg = f"Scraping failed: {str(e)}"
            logger.error(error_msg)

            source.last_error = error_msg
            source.save()

            return {
                "success": False,
                "articles_found": 0,
                "articles_new": 0,
                "error": error_msg,
            }

    @staticmethod
    def _process_entry(source: CASource, entry: Dict[str, Any]) -> bool:
        """
        Process a single RSS entry
        """
        # Extract fields
        title = entry.get("title", "").strip()
        url = entry.get("link", "").strip()

        if not title or not url:
            return False

        # Check if already exists
        if CAArticle.objects.filter(url=url).exists():
            return False

        # Extract content
        # Priority: content > summary > description
        content = ""

        # 1. Try 'content' list (common in Atom/RSS 2.0)
        if (
            hasattr(entry, "content")
            and isinstance(entry.content, list)
            and entry.content
        ):
            # Try to find html/text content
            for c in entry.content:
                if c.get("value"):
                    content = c.get("value")
                    break

        # 2. Try 'summary_detail'
        if not content and hasattr(entry, "summary_detail") and entry.summary_detail:
            content = entry.summary_detail.get("value", "")

        # 3. Try 'summary' (fallback)
        if not content and hasattr(entry, "summary"):
            content = entry.summary

        # 4. Try 'description'
        if not content:
            content = entry.get("description", "")

        # 5. Fallback: Fetch full page content if RSS content is empty or too short
        if not content or len(content.strip()) < 50:
            try:
                fetched = RSSScraperService._fetch_full_content(url)
                if fetched:
                    content = fetched
                    # logger.info(f"Fetched full content for '{title}' (Length: {len(content)})")
            except Exception as e:
                sentry_sdk.capture_exception(e)
                logger.debug(f"Failed to fetch full content for {url}: {str(e)}")

        # Clean content (basic checks)
        if not content or len(content.strip()) < 10:
            logger.warning(
                f"Skipping article '{title}' - No robust content found. (Content len: {len(content) if content else 0})",
                extra={"source": source.name, "url": url},
            )
            return False

        # Extract published date
        published_at = timezone.now()  # Default
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published_at = datetime(*entry.published_parsed[:6])
                if timezone.is_naive(published_at):
                    published_at = timezone.make_aware(published_at)
            except Exception as e:
                sentry_sdk.capture_exception(e)
                logger.debug(f"Failed to parse published date: {str(e)}")  # nosec: B110
                pass  # Fallback to now

        # Extract author
        author = entry.get("author", "")

        # Extract categories
        categories = []
        if hasattr(entry, "tags"):
            categories = [tag.get("term", "") for tag in entry.tags]

        # Calculate word count
        word_count = len(content.split())

        # Create article
        try:
            with transaction.atomic():
                CAArticle.objects.create(
                    source=source,
                    title=title,
                    url=url,
                    content=content,
                    published_at=published_at,
                    author=author[:200],  # Truncate if too long
                    categories=categories,
                    word_count=word_count,
                    processing_status="pending",
                )

            logger.info(f"Created CA article: {title}")
            return True

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Error creating article {title}: {str(e)}")
            return False

    @staticmethod
    def _fetch_full_content(url: str) -> str:
        """
        Fetch full page content for articles where RSS feed is truncated/empty.
        """
        try:
            # Basic headers to mimic browser
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            # Timeout is critical to avoid hanging
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")

                # Heuristic to find article content
                # 1. Try common article body selectors
                selectors = [
                    "div.story-details",
                    "div.full-details",
                    "article",
                    "div.article-body",
                    "div.content",
                    "div.story_details",
                ]

                for selector in selectors:
                    element = soup.select_one(selector)
                    if element:
                        # Extract paragraphs
                        paragraphs = element.find_all("p")
                        if paragraphs:
                            return " ".join([p.get_text().strip() for p in paragraphs])

                # 2. Fallback: Just grab large paragraphs
                paragraphs = soup.find_all("p")
                if paragraphs:
                    # Filter out very short UI texts.
                    # Only keep p tags with substantial content (> 50 chars) to avoid navigational noise.
                    valid_ps = [
                        p.get_text().strip()
                        for p in paragraphs
                        if len(p.get_text().strip()) > 50
                    ]
                    if valid_ps:
                        return " ".join(valid_ps)

            return ""

        except Exception:
            sentry_sdk.capture_message("Handled Exception without var")
            # Silent failure - returning empty string allows graceful degradation
            return ""

    @staticmethod
    def scrape_all_active() -> Dict[str, Any]:
        """
        Scrape all active RSS sources
        """
        results: Dict[str, Any] = {
            "sources_scraped": 0,
            "sources_success": 0,
            "sources_failed": 0,
            "articles_found": 0,
            "articles_new": 0,
            "errors": [],
        }

        sources = CASource.objects.filter(is_active=True)

        for source in sources:
            results["sources_scraped"] += 1
            result = RSSScraperService.scrape_source(source)

            results["articles_found"] += result["articles_found"]
            results["articles_new"] += result["articles_new"]

            if result["success"]:
                results["sources_success"] += 1
            else:
                results["sources_failed"] += 1
                results["errors"].append(
                    {"source": source.name, "error": result["error"]}
                )

        return results
