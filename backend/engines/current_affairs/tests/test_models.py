import uuid
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

import pytest

from engines.current_affairs.models import CAArticle, CAChunk, CASource, CATopicLink
from engines.knowledge.models import Module, Program, Subject, Topic


@pytest.fixture
def ca_source():
    """Create CA source."""
    return CASource.objects.create(
        name=f"The Hindu {uuid.uuid4()}",
        source_type="rss",
        url=f"https://www.thehindu.com/news/national/feeder/default-{uuid.uuid4()}.rss",
        is_active=True,
        scrape_frequency="daily",
    )


@pytest.fixture
def topic():
    """Create test topic."""
    uid = str(uuid.uuid4())[:8]
    program = Program.objects.create(name=f"Program-{uid}")
    subject = Subject.objects.create(name=f"Subject-{uid}", program=program)
    module = Module.objects.create(name=f"Module-{uid}", subject=subject)
    return Topic.objects.create(name=f"Topic-{uid}", module=module, subject=subject)


@pytest.mark.django_db
class TestCASourceModel:
    """Test CASource model."""

    def test_create_source(self):
        """Test creating CA source."""
        uid = str(uuid.uuid4())[:8]
        source = CASource.objects.create(
            name=f"Unique Source {uid}",
            source_type="rss",
            url=f"https://example.com/rss-{uid}",
            is_active=True,
        )

        assert "Unique Source" in source.name
        assert source.is_active
        assert source.article_count == 0

    def test_source_has_uuid(self):
        """Test source has UUID primary key."""
        uid = str(uuid.uuid4())[:8]
        source = CASource.objects.create(
            name=f"Test {uid}", url=f"https://test.com/rss-{uid}"
        )

        assert isinstance(source.id, uuid.UUID)


@pytest.mark.django_db
class TestCAArticleModel:
    """Test CAArticle model."""

    def test_create_article(self, ca_source):
        """Test creating CA article."""
        article = CAArticle.objects.create(
            source=ca_source,
            title="Test Article",
            url=f"https://example.com/article-{uuid.uuid4()}",
            content="Article content here",
            published_at=timezone.now(),
            word_count=100,
            processing_status="pending",
        )

        assert article.title == "Test Article"
        assert article.processing_status == "pending"
        # Check auto-summary from the model save() method
        assert article.summary == "Article content here"

    def test_unique_url_constraint(self, ca_source):
        """Test article URL must be unique."""
        url = f"https://example.com/unique-{uuid.uuid4()}"

        CAArticle.objects.create(
            source=ca_source,
            title="Article 1",
            url=url,
            content="Content",
            published_at=timezone.now(),
        )

        # Use transaction.atomic to prevent dirtying the main test transaction
        with transaction.atomic():
            with pytest.raises(IntegrityError):
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
            url=f"https://example.com/chunk-test-{uuid.uuid4()}",
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
        published = timezone.now()
        article = CAArticle.objects.create(
            source=ca_source,
            title="Test",
            url=f"https://example.com/expiry-test-{uuid.uuid4()}",
            content="Content",
            published_at=published,
        )

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
            url=f"https://example.com/link-test-{uuid.uuid4()}",
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
            url=f"https://example.com/unique-link-test-{uuid.uuid4()}",
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

        # Use transaction.atomic to prevent dirtying the main test transaction
        with transaction.atomic():
            with pytest.raises(IntegrityError):
                CATopicLink.objects.create(ca_chunk=chunk, topic=topic)
