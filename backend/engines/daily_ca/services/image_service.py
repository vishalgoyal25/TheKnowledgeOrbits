"""
engines/daily_ca/services/image_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase J — Hero Image Pipeline.

Fetches a topic-relevant hero image for each generated Daily CA article,
uploads it to Cloudinary, and returns the secure URL for storage.

Fetch order (per product decision):
  1. Unsplash API search by topic_name  (primary — diverse, legal, copyright-free)
  2. Wikipedia thumbnail for topic_name (fallback — specific Indian political topics)
  3. Return "" if both fail             (no image, never blocks article generation)

Design constraints:
  - NEVER raises — image failure must not block or fail article generation
  - HTTP timeout: 5 seconds per request (safe for Render cron jobs)
  - Unsplash: landscape orientation preferred, first result used
  - Cloudinary upload uses article UUID as public_id → idempotent re-runs
  - All errors are caught, logged with structlog, and captured in Sentry
"""

import os

import sentry_sdk
import structlog

logger = structlog.get_logger(__name__)

# HTTP timeout (seconds) per external request.
_HTTP_TIMEOUT = 5

# Cloudinary folder for all daily CA hero images.
_CLOUDINARY_FOLDER = "daily_ca_heroes"

# Unsplash API base URL.
_UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"


class HeroImageService:
    """
    Fetches and uploads hero images for Daily CA articles.

    Usage (called from generator_service.py after _run_single_cycle):
        hero_url = HeroImageService.fetch_and_upload(
            source_urls=proposal.source_urls or [],
            topic_name=topic_name,
            article_id=str(article.id),
        )
    """

    @staticmethod
    def fetch_and_upload(
        source_urls: list[dict],
        topic_name: str,
        article_id: str,
    ) -> str:
        """
        Main entry point. Returns Cloudinary secure_url or "" if nothing found.
        Never raises.

        Args:
            source_urls: list of {source_name, url, title} dicts (unused now — kept
                         for API compatibility with generator_service.py)
            topic_name:  used as Unsplash search query and Wikipedia fallback
            article_id:  UUID string — used as Cloudinary public_id (idempotent)
        """
        try:
            image_url = HeroImageService._try_unsplash(
                topic_name
            ) or HeroImageService._try_wikipedia_thumbnail(topic_name)

            if not image_url:
                logger.info(
                    "hero_image_no_source_found",
                    article_id=article_id,
                    topic=topic_name[:60],
                )
                return ""

            return HeroImageService._upload_to_cloudinary(image_url, article_id)

        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.warning(
                "hero_image_fetch_failed",
                article_id=article_id,
                error=str(exc)[:200],
            )
            return ""

    # ── Layer 1: Unsplash search ──────────────────────────────────────────────

    @staticmethod
    def _try_unsplash(topic_name: str) -> str:
        """
        Searches Unsplash for a landscape photo matching the topic.
        Returns the 'regular' size URL (1080px) of the first result, or "".

        Two-pass strategy:
          Pass 1 — full topic_name (specific, best match)
          Pass 2 — simplified keyword query (broader, fallback for Indian-specific
                   terms like "Lok Sabha" or "Partition of Bengal" that return 0
                   results on Unsplash's English-centric photo library)

        Uses UNSPLASH_ACCESS_KEY from environment.
        API docs: https://unsplash.com/documentation#search-photos
        """
        access_key = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
        if not access_key:
            logger.warning("hero_image_unsplash_key_missing")
            return ""

        if not topic_name or not topic_name.strip():
            return ""

        try:
            # ── Pass 1: full topic name ───────────────────────────────────────
            result = HeroImageService._unsplash_query(
                access_key, topic_name.strip(), topic_name
            )
            if result:
                return result

            # ── Pass 2: simplified keyword fallback ───────────────────────────
            # Extract the 1-2 most distinctive words (longest, non-stopword).
            # "Partition of Bengal" → "Partition Bengal"
            # "Lok Sabha Speaker" → "Parliament India"  (uses subject fallback)
            # "Electoral Reforms Commission" → "Electoral Commission"
            simplified = _simplify_query(topic_name)
            if simplified and simplified.lower() != topic_name.strip().lower():
                result = HeroImageService._unsplash_query(
                    access_key, simplified, topic_name
                )
                if result:
                    logger.info(
                        "hero_image_unsplash_fallback_used",
                        topic=topic_name[:60],
                        fallback_query=simplified,
                    )
                    return result

            logger.info(
                "hero_image_unsplash_no_results",
                topic=topic_name[:60],
            )

        except Exception as exc:
            logger.info(
                "hero_image_unsplash_failed",
                topic=topic_name[:60],
                error=str(exc)[:100],
            )

        return ""

    @staticmethod
    def _unsplash_query(access_key: str, query: str, topic_name: str) -> str:
        """
        Single Unsplash API call for `query`.
        Returns URL of first valid result, or "" if none.
        """
        import requests

        resp = requests.get(
            _UNSPLASH_SEARCH_URL,
            params={
                "query": query,
                "per_page": "5",  # fetch 5, pick first valid
                "orientation": "landscape",
                "content_filter": "high",  # safe content only
            },
            headers={"Authorization": f"Client-ID {access_key}"},
            timeout=_HTTP_TIMEOUT,
        )

        if resp.status_code != 200:
            logger.info(
                "hero_image_unsplash_api_error",
                status=resp.status_code,
                topic=topic_name[:60],
                query=query,
            )
            return ""

        results = resp.json().get("results", [])
        for photo in results:
            urls = photo.get("urls", {})
            url = urls.get("regular", "") or urls.get("full", "")
            if url and url.startswith("http") and _is_valid_image_url(url):
                logger.info(
                    "hero_image_unsplash_found",
                    topic=topic_name[:60],
                    query=query,
                    photo_id=photo.get("id", ""),
                )
                return url

        return ""

    # ── Layer 2: Wikipedia thumbnail ─────────────────────────────────────────

    @staticmethod
    def _try_wikipedia_thumbnail(topic_name: str) -> str:
        """
        Calls Wikipedia REST API for the topic's page thumbnail.
        Returns thumbnail URL or "".

        API: GET https://en.wikipedia.org/api/rest_v1/page/summary/{title}
        Response JSON contains thumbnail.source for the lead image.
        Fast, lightweight — single HTTP call, no scraping.
        """
        if not topic_name or not topic_name.strip():
            return ""

        try:
            import requests

            # Normalise: replace spaces with underscores for Wikipedia API
            wiki_title = topic_name.strip().replace(" ", "_")
            api_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{wiki_title}"

            resp = requests.get(
                api_url,
                timeout=_HTTP_TIMEOUT,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "TheKnowledgeOrbits/1.0 (contact@theknowledgeorbits.com)",
                },
            )
            if resp.status_code != 200:
                return ""

            data = resp.json()
            thumbnail = data.get("thumbnail", {})
            source = thumbnail.get("source", "")

            if source and source.startswith("http") and _is_valid_image_url(source):
                logger.info(
                    "hero_image_wikipedia_found",
                    topic=topic_name[:60],
                    image_url=source[:80],
                )
                return source

        except Exception as exc:
            logger.info(
                "hero_image_wikipedia_failed",
                topic=topic_name[:60],
                error=str(exc)[:100],
            )

        return ""

    # ── Cloudinary upload ─────────────────────────────────────────────────────

    @staticmethod
    def _upload_to_cloudinary(image_url: str, article_id: str) -> str:
        """
        Downloads image from image_url and uploads to Cloudinary.
        Uses article_id as public_id → idempotent: re-running won't duplicate images.

        Returns Cloudinary secure_url or "" on failure.
        """
        try:
            import cloudinary
            import cloudinary.uploader
            from django.conf import settings

            # Ensure Cloudinary is configured (reads CLOUDINARY_STORAGE from settings)
            cloud_cfg = getattr(settings, "CLOUDINARY_STORAGE", {})
            if not cloud_cfg.get("CLOUD_NAME"):
                logger.warning("hero_image_cloudinary_not_configured")
                return ""

            cloudinary.config(
                cloud_name=cloud_cfg["CLOUD_NAME"],
                api_key=cloud_cfg["API_KEY"],
                api_secret=cloud_cfg["API_SECRET"],
                secure=True,
            )

            # public_id = ca_{article_id} — deterministic, prevents duplicates
            public_id = f"ca_{article_id.replace('-', '_')}"

            result = cloudinary.uploader.upload(
                image_url,
                folder=_CLOUDINARY_FOLDER,
                public_id=public_id,
                overwrite=False,  # idempotent — skip if already uploaded
                resource_type="image",
                fetch_format="auto",  # serve WebP where supported
                quality="auto:good",  # balanced quality/size
                width=1200,
                crop="limit",  # never upscale, just cap at 1200px wide
            )

            secure_url = result.get("secure_url", "")
            if secure_url:
                logger.info(
                    "hero_image_cloudinary_uploaded",
                    article_id=article_id,
                    cloudinary_url=secure_url[:100],
                    public_id=public_id,
                )
            return secure_url

        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.warning(
                "hero_image_cloudinary_upload_failed",
                article_id=article_id,
                image_url=image_url[:80],
                error=str(exc)[:200],
            )
            return ""


# ── Helpers ───────────────────────────────────────────────────────────────────


def _is_valid_image_url(url: str) -> bool:
    """
    Basic guard — rejects data URIs, SVGs (including .svg.png Wikipedia renders),
    diagrams, and tiny tracking pixels.
    Does NOT make an HTTP request — purely string-based check.
    """
    url_lower = url.lower()
    if url_lower.startswith("data:"):
        return False
    # Reject SVGs and Wikipedia's SVG-rendered-as-PNG (e.g. "diagram.svg/330px-diagram.svg.png")
    if ".svg" in url_lower:
        return False
    # Reject tracking pixels
    if any(p in url_lower for p in ("/pixel/", "/beacon/", "/track/", "1x1")):
        return False
    return True


def _simplify_query(topic_name: str) -> str:
    """
    Builds a simpler Unsplash search query from a topic name.

    Strategy:
      1. Strip common stopwords and short connector words.
      2. Keep the 2 longest remaining words (most topically distinctive).
      3. Map well-known Indian-specific terms to Unsplash-friendly equivalents.

    Examples:
      "Lok Sabha"                → "Parliament India"
      "Partition of Bengal"      → "Bengal history"
      "Electoral Reforms Bill"   → "Electoral Reforms"
      "MGNREGA Rural Employment" → "Rural Employment"
    """
    _STOPWORDS = {
        "of",
        "the",
        "a",
        "an",
        "in",
        "to",
        "and",
        "for",
        "on",
        "at",
        "is",
        "are",
        "was",
        "were",
        "by",
        "with",
        "as",
        "from",
        "that",
        "this",
        "its",
        "over",
        "after",
        "amid",
        "under",
        "into",
        "through",
    }

    # Hard mappings for Indian governance terms that Unsplash has no photos for
    _TERM_MAP = {
        "lok sabha": "parliament india",
        "rajya sabha": "parliament india",
        "lok sabha speaker": "parliament india",
        "sansad": "parliament india",
        "vidhan sabha": "state legislature india",
    }

    lower = topic_name.strip().lower()

    # Check hard-map first (exact match)
    if lower in _TERM_MAP:
        return _TERM_MAP[lower]

    # Check if any hard-map key is a substring
    for key, replacement in _TERM_MAP.items():
        if key in lower:
            return replacement

    # Generic: strip stopwords, keep 2 longest meaningful words
    words = [
        w.strip(".,:-—\"'()")
        for w in topic_name.split()
        if w.lower().strip(".,:-—\"'()") not in _STOPWORDS
        and len(w.strip(".,:-—\"'()")) > 3
    ]

    if not words:
        return topic_name.strip()

    # Sort by word length descending — longer words are usually more specific nouns
    words_by_len = sorted(words, key=len, reverse=True)
    top_words = words_by_len[:2]

    return " ".join(top_words)
