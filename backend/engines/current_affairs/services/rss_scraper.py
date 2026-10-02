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

# Full browser fingerprint, not just a User-Agent.
#
# 2026-10-02: Indian Express returned HTTP 403 to the GitHub Actions runner
# while serving the same URL fine from a home connection. Edge bot-protection
# (Cloudflare/Akamai class) scores the WHOLE header set, not the UA alone — a
# request carrying only UA/Accept/Accept-Language looks nothing like a browser.
# Sending the Sec-Fetch-* and Upgrade-Insecure-Requests headers a real Chrome
# sends, over a Session (so any challenge cookie is kept), is the cheapest
# thing that can plausibly pass. It may still not: see FEED_FALLBACK_NOTE.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "application/rss+xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

FEED_TIMEOUT_SECONDS = 20

# U+FFFD. Its presence in decoded text means bytes were lost in the decode and
# the text can no longer be trusted as a citation source — see the encoding
# note in _fetch_full_content.
REPLACEMENT_CHAR = "�"

# FEED_FALLBACK_NOTE
# If a publisher blocks by IP RANGE rather than by request shape, no header set
# will help — the GitHub Actions runner simply is not welcome. That is a
# sourcing decision, not a code fix: move the source to a different execution
# context, swap to a feed path that is not behind the same edge rule, or drop
# it. Indian Express is a Tier 3 discovery source (never cited as evidence), so
# losing it costs event discovery, not factual coverage.
#
# Either way a blocked source must NEVER take the run down: scrape_all_active()
# continues, and the failure is recorded against this source alone.


class RSSScraperService:
    """RSS feed scraping service"""

    @staticmethod
    def _fetch_feed(source: CASource) -> Any:
        """
        Fetch and parse one feed.

        Order of attempts:
          1. `requests` with a full browser fingerprint, over a Session.
          2. On a non-200, feedparser's own fetch — a different request shape,
             which occasionally passes where ours does not.
          3. On total failure, return None so the caller can report the real
             HTTP status instead of a bogus XML error.

        ⚠️ A non-200 body is NEVER parsed. Feeding an HTML error page to an XML
        parser is what produced the misleading "mismatched tag at <unknown>:5:2"
        that masked a plain 403 for weeks.
        """
        status: Any = None
        try:
            with requests.Session() as session:
                session.headers.update(BROWSER_HEADERS)
                response = session.get(source.url, timeout=FEED_TIMEOUT_SECONDS)
            status = response.status_code

            if status == 200:
                return feedparser.parse(response.content)

            logger.warning(
                "feed_http_error",
                source_name=source.name,
                status=status,
                note="non-200 body not parsed; trying feedparser direct",
            )
        except Exception as exc:
            logger.warning(
                "feed_http_fetch_failed", source_name=source.name, error=str(exc)
            )

        # Attempt 2 — feedparser's own fetch. Different header shape, so it
        # sometimes succeeds where ours is refused. Cheap to try.
        try:
            feed = feedparser.parse(source.url)
            if feed.entries:
                logger.info(
                    "feed_recovered_via_feedparser",
                    source_name=source.name,
                    blocked_status=status,
                    entries=len(feed.entries),
                )
                return feed
        except Exception as exc:
            logger.warning(
                "feed_direct_fetch_failed", source_name=source.name, error=str(exc)
            )

        # Both paths refused. Returning None lets the caller report the HTTP
        # status honestly rather than inventing an XML parse error.
        logger.error(
            "feed_blocked",
            source_name=source.name,
            status=status,
            hint=(
                "Edge bot-protection or IP-range block. If this persists from "
                "CI but works locally, it is the runner's IP — see "
                "FEED_FALLBACK_NOTE."
            ),
        )
        return None

    @staticmethod
    def scrape_source(source: CASource) -> Dict[str, Any]:
        """
        Scrape a single source
        """
        logger.info("scraping_source", source_name=source.name)

        try:
            feed = RSSScraperService._fetch_feed(source)

            # _fetch_feed returns None when every fetch path was refused
            # (403 / 429 / network). Report the block honestly; do NOT invent
            # an XML parse error from an HTML error page.
            if feed is None:
                error_msg = "Feed fetch blocked or unreachable (see feed_blocked log)"
                source.last_error = error_msg
                source.save()
                return {
                    "success": False,
                    "articles_found": 0,
                    "articles_new": 0,
                    "error": error_msg,
                }

            # `bozo` is set by ANY well-formedness warning — a stray ampersand,
            # a smart quote, one malformed item. feedparser's loose parser
            # almost always still extracts the entries. Treating bozo alone as
            # fatal threw away the whole source on the first complaint, which
            # is what killed Indian Express on 2026-09-28 ("mismatched tag" at
            # <unknown>:5:2) while the feed was otherwise fine — verified
            # 2026-10-02: the same URL parses 200 entries with bozo=False.
            #
            # A feed is only genuinely broken when nothing parsed out of it.
            if feed.bozo and not feed.entries:
                bozo_exc = getattr(feed, "bozo_exception", None)
                error_msg = f"Feed parsing error: {bozo_exc}"
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

            if feed.bozo:
                # Malformed but usable — record it and carry on.
                logger.warning(
                    "feed_malformed_but_usable",
                    source_name=source.name,
                    entries=len(feed.entries),
                    error=str(getattr(feed, "bozo_exception", "")),
                )

            if not feed.entries:
                error_msg = "Feed returned no entries"
                logger.error("feed_empty", error=error_msg, source_name=source.name)
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
            # Same browser headers as the feed fetch (BROWSER_HEADERS), but
            # asking for HTML rather than XML.
            headers = {
                **BROWSER_HEADERS,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
            # Timeout is critical to avoid hanging
            response = requests.get(url, headers=headers, timeout=12)

            if response.status_code == 200:
                # ── ENCODING (fixed 2026-10-02) ──────────────────────────────
                # Passing response.content (BYTES) made BeautifulSoup guess the
                # encoding with UnicodeDammit, which emitted "Some characters
                # could not be decoded ... replaced with REPLACEMENT CHARACTER"
                # on every article and silently corrupted the body text.
                #
                # Why it happened: `requests` follows RFC 2616 and defaults
                # `response.encoding` to ISO-8859-1 whenever a text/* response
                # carries no charset in its Content-Type. Indian news sites are
                # UTF-8, so curly quotes, em dashes and diacritics in names were
                # mangled before anything else ran.
                #
                # 🔴 This is not cosmetic for the Data Factory. Corrupted bytes
                # mean corrupted chunk text, which means atom `char_span`
                # offsets that point at garbage. The verification contract
                # depends on the stored text being byte-exact.
                if not response.encoding or response.encoding.lower() in (
                    "iso-8859-1",
                    "latin-1",
                    "latin1",
                ):
                    detected = response.apparent_encoding
                    if detected:
                        response.encoding = detected

                html = response.text

                # Make corruption VISIBLE rather than silent. If replacement
                # characters survived the decode, the text is already damaged
                # and must not be trusted as a citation source.
                if REPLACEMENT_CHAR in html:
                    logger.warning(
                        "content_encoding_degraded",
                        url=url,
                        declared=response.headers.get("Content-Type"),
                        used=response.encoding,
                        replacement_chars=html.count(REPLACEMENT_CHAR),
                    )

                soup = BeautifulSoup(html, "html.parser")

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

        if results["articles_new"] > 0:
            from django.core.cache import cache

            cache.delete("ca_articles_page_1")

            # Invalidate all count query caches for ca_article
            try:
                if hasattr(cache, "delete_pattern"):
                    cache.delete_pattern("q_count_ca_article_*")
                else:
                    cache.delete("ca_articles_total_count")
            except Exception:
                pass

        return results
