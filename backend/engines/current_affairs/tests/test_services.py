"""
Current Affairs Engine - Service Tests

Tests for RSSScraperService, CAProcessorService, TopicLinkerService.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from django.utils import timezone
from engines.current_affairs.models import CASource, CAArticle, CAChunk
from engines.current_affairs.services.rss_scraper import RSSScraperService
from engines.current_affairs.services.ca_processor import CAProcessorService
from engines.current_affairs.services.topic_linker import TopicLinkerService


@pytest.fixture
def ca_source():
    return CASource.objects.create(
        name="Test Source", url="https://test.com/rss", is_active=True
    )


@pytest.mark.django_db
class TestRSSScraperService:
    """Test RSSScraperService."""

    @patch("engines.current_affairs.services.rss_scraper.feedparser.parse")
    def test_scrape_source_success(self, mock_parse, ca_source):
        """Test successful RSS scraping."""
        # Mock feedparser response
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[
                {
                    "title": "Test Article",
                    "link": "https://test.com/article1",
                    "summary": "Article summary content here",
                    "published_parsed": datetime.now().timetuple(),
                }
            ],
        )

        result = RSSScraperService.scrape_source(ca_source)

        assert result["success"]
        assert result["articles_found"] == 1

    @patch("engines.current_affairs.services.rss_scraper.feedparser.parse")
    def test_scrape_duplicate_article(self, mock_parse, ca_source):
        """Test scraping duplicate article (already exists)."""
        # Create existing article
        CAArticle.objects.create(
            source=ca_source,
            title="Existing",
            url="https://test.com/article1",
            content="Content",
            published_at=timezone.now(),
        )

        # Mock feedparser with duplicate URL
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[
                {
                    "title": "Test Article",
                    "link": "https://test.com/article1",
                    "summary": "Content",
                    "published_parsed": datetime.now().timetuple(),
                }
            ],
        )

        result = RSSScraperService.scrape_source(ca_source)

        assert result["articles_new"] == 0  # Duplicate skipped


@pytest.mark.django_db
class TestCAProcessorService:
    """Test CAProcessorService."""

    def test_process_article(self, ca_source):
        """Test processing CA article into chunks."""
        article = CAArticle.objects.create(
            source=ca_source,
            title="Test Article",
            url="https://test.com/article",
            content="This is test content. " * 100,  # ~2000 chars
            published_at=timezone.now(),
        )

        success = CAProcessorService.process_article(article)

        assert success
        article.refresh_from_db()
        assert article.processing_status == "completed"
        assert article.chunk_count > 0

    def test_chunk_content(self):
        """Test content chunking."""
        content = "Test sentence. " * 100  # ~1500 chars

        chunks = CAProcessorService._chunk_content(content)

        assert len(chunks) >= 1
        assert all(len(c) >= CAProcessorService.MIN_CHUNK_SIZE for c in chunks)


@pytest.mark.django_db
class TestTopicLinkerService:
    """Test TopicLinkerService."""

    def test_cosine_similarity(self):
        """Test cosine similarity calculation."""
        import numpy as np

        v1 = np.array([1.0, 0.0, 0.0])
        v2 = np.array([1.0, 0.0, 0.0])

        sim = TopicLinkerService._cosine_similarity(v1, v2)

        assert sim == 1.0

    def test_orthogonal_vectors(self):
        """Test orthogonal vectors have zero similarity."""
        import numpy as np

        v1 = np.array([1.0, 0.0, 0.0])
        v2 = np.array([0.0, 1.0, 0.0])

        sim = TopicLinkerService._cosine_similarity(v1, v2)

        assert sim == 0.0
