"""
Current Affairs Engine - Model Tests

Tests for CASource, CAArticle, CAChunk, CATopicLink models.
"""

import uuid
from datetime import timedelta

from django.utils import timezone

import pytest

from engines.current_affairs.models import CAArticle, CAChunk, CASource, CATopicLink
from engines.knowledge.models import Module, Program, Subject, Topic


@pytest.fixture
def ca_source():
    """Create CA source."""
    return CASource.objects.create(
        name="The Hindu",
        source_type="rss",
        url="https://www.thehindu.com/news/national/feeder/default.rss",
        is_active=True,
        scrape_frequency="daily",
    )


@pytest.fixture
def topic():
    """Create test topic."""
    program = Program.objects.create(name="UPSC CSE")
    subject = Subject.objects.create(name="Polity", program=program)
    module = Module.objects.create(name="Constitution", subject=subject)
    return Topic.objects.create(name="Article 370", module=module, subject=subject)


@pytest.mark.django_db
class TestCASourceModel:
    """Test CASource model."""

    def test_create_source(self):
        """Test creating CA source."""
        source = CASource.objects.create(
            name="The Hindu",
            source_type="rss",
            url="https://example.com/rss",
            is_active=True,
        )

        assert source.name == "The Hindu"
        assert source.is_active
        assert source.article_count == 0

    def test_source_has_uuid(self):
        """Test source has UUID primary key."""
        source = CASource.objects.create(name="Test Source", url="https://test.com/rss")

        assert isinstance(source.id, uuid.UUID)


@pytest.mark.django_db
class TestCAArticleModel:
    """Test CAArticle model."""

    def test_create_article(self, ca_source):
        """Test creating CA article."""
        article = CAArticle.objects.create(
            source=ca_source,
            title="Test Article",
            url="https://example.com/article1",
            content="Article content here",
            published_at=timezone.now(),
            word_count=100,
            processing_status="pending",
        )

        assert article.title == "Test Article"
        assert article.processing_status == "pending"

    def test_unique_url_constraint(self, ca_source):
        """Test article URL must be unique."""
        url = "https://example.com/article1"

        CAArticle.objects.create(
            source=ca_source,
            title="Article 1",
            url=url,
            content="Content",
            published_at=timezone.now(),
        )

        with pytest.raises(Exception):  # IntegrityError
            CAArticle.objects.create(
                source=ca_source,
                title="Article 2",
                url=url,
                content="Different content",
                published_at=timezone.now(),
            )


@pytest.mark.django_db
class TestCAChunkModel:
    """Test CAChunk model."""

    def test_create_chunk(self, ca_source):
        """Test creating CA chunk."""
        article = CAArticle.objects.create(
            source=ca_source,
            title="Test Article",
            url="https://example.com/article1",
            content="Content",
            published_at=timezone.now(),
        )

        chunk = CAChunk.objects.create(
            ca_article=article,
            chunk_text="Chunk content",
            chunk_index=0,
            source_type="dynamic",
            published_at=timezone.now(),
        )

        assert chunk.source_type == "dynamic"
        assert chunk.chunk_index == 0

    def test_expiry_date_auto_set(self, ca_source):
        """Test expiry date auto-sets to 180 days."""
        article = CAArticle.objects.create(
            source=ca_source,
            title="Test",
            url="https://example.com/test",
            content="Content",
            published_at=timezone.now(),
        )

        published = timezone.now()
        chunk = CAChunk.objects.create(
            ca_article=article,
            chunk_text="Content",
            chunk_index=0,
            published_at=published,
        )

        expected_expiry = published + timedelta(days=180)

        # Allow 1 second tolerance
        assert abs((chunk.expiry_date - expected_expiry).total_seconds()) < 1


@pytest.mark.django_db
class TestCATopicLinkModel:
    """Test CATopicLink model."""

    def test_create_link(self, ca_source, topic):
        """Test creating CA topic link."""
        article = CAArticle.objects.create(
            source=ca_source,
            title="Test",
            url="https://example.com/test",
            content="Content",
            published_at=timezone.now(),
        )

        chunk = CAChunk.objects.create(
            ca_article=article,
            chunk_text="Article 370 content",
            chunk_index=0,
            published_at=timezone.now(),
        )

        link = CATopicLink.objects.create(
            ca_chunk=chunk, topic=topic, relevance_score=0.85, link_method="auto"
        )

        assert link.relevance_score == 0.85
        assert link.link_method == "auto"

    def test_unique_chunk_topic_link(self, ca_source, topic):
        """Test chunk-topic link uniqueness."""
        article = CAArticle.objects.create(
            source=ca_source,
            title="Test",
            url="https://example.com/test",
            content="Content",
            published_at=timezone.now(),
        )

        chunk = CAChunk.objects.create(
            ca_article=article,
            chunk_text="Content",
            chunk_index=0,
            published_at=timezone.now(),
        )

        CATopicLink.objects.create(ca_chunk=chunk, topic=topic)

        with pytest.raises(Exception):  # IntegrityError
            CATopicLink.objects.create(ca_chunk=chunk, topic=topic)
