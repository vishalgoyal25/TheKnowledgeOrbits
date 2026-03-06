import sentry_sdk

"""
RSS Scraper Service

Scrapes RSS feeds from news sources
"""

from datetime import datetime
from typing import Any, Dict

import feedparser
import requests
import structlog
from bs4 import BeautifulSoup
from django.db import transaction
from django.utils import timezone

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
        # Priority 1: Actively fetch the full article page (for TH and IE full text)
        content = ""
        try:
            fetched = RSSScraperService._fetch_full_content(url)
            if fetched and len(fetched.strip()) > 300:
                content = fetched
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.debug(f"Failed to fetch full content for {url}: {str(e)}")

        # Priority 2: Fallback to RSS feed content if full page fetch fails or is blocked
        if not content:
            # Try 'content' list (common in Atom/RSS 2.0)
            if (
                hasattr(entry, "content")
                and isinstance(entry.content, list)
                and entry.content
            ):
                for c in entry.content:
                    if c.get("value"):
                        content = c.get("value")
                        break

            # Try 'summary_detail'
            if (
                not content
                and hasattr(entry, "summary_detail")
                and entry.summary_detail
            ):
                content = entry.summary_detail.get("value", "")

            # Try 'summary' (fallback)
            if not content and hasattr(entry, "summary"):
                content = entry.summary

            # Try 'description'
            if not content:
                content = entry.get("description", "")

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
                import datetime as dt

                parsed_dt = datetime(*entry.published_parsed[:6])
                if timezone.is_naive(parsed_dt):
                    # RSS feeds always parse as UTC. Force UTC aware, NOT local timezone.
                    published_at = parsed_dt.replace(tzinfo=dt.timezone.utc)
                else:
                    published_at = parsed_dt
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

        # Create summary from content for safe list rendering
        summary = (content[:150] + "...") if len(content) > 150 else content

        # Create article
        try:
            with transaction.atomic():
                CAArticle.objects.create(
                    source=source,
                    title=title,
                    url=url,
                    content=content,
                    summary=summary,
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
            # Modern headers to mimic a real browser to bypass basic bot blocks (Cloudflare, etc.)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
            # Timeout is critical to avoid hanging
            response = requests.get(url, headers=headers, timeout=12)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")

                # Heuristic to find article content specifically targeting TH and IE
                # The Hindu: div.articlebodycontent, class^=content-body
                # Indian Express: div#pcl-full-content, div.story_details
                selectors = [
                    "div.articlebodycontent",
                    "div[id^='content-body']",
                    "div#pcl-full-content",
                    "div.story_details",
                    "div.story-details",
                    "div.full-details",
                    "article",
                    "div.article-body",
                    "div.content",
                ]

                for selector in selectors:
                    element = soup.select_one(selector)
                    if element:
                        # Extract paragraphs securely without scripts/styles
                        for s in element(
                            ["script", "style", "nav", "header", "footer"]
                        ):
                            s.decompose()

                        paragraphs = element.find_all("p")
                        if paragraphs:
                            valid_ps = [
                                p.get_text().strip()
                                for p in paragraphs
                                if len(p.get_text().strip()) > 30
                            ]
                            if valid_ps:
                                return " ".join(valid_ps)

                # 2. Fallback: Just grab large paragraphs from the whole page
                paragraphs = soup.find_all("p")
                if paragraphs:
                    # Filter out very short UI texts. (Ads, nav links, etc.)
                    valid_ps = [
                        p.get_text().strip()
                        for p in paragraphs
                        if len(p.get_text().strip()) > 80
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
