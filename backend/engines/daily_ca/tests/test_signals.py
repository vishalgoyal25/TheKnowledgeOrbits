"""
engines/daily_ca/tests/test_signals.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tests for engines/daily_ca/signals.py

Covers:
  - on_daily_ca_article_save: thread started when is_published=True
  - on_daily_ca_article_save: no thread when is_published=False
  - on_daily_ca_article_save: no thread when text is empty
  - _generate_and_save_embedding: skips if embedding already exists (idempotent)
  - _generate_and_save_embedding: creates embedding when none exists
  - _generate_and_save_embedding: swallows exceptions (never raises)

All EmbeddingService calls are mocked — no HF API calls in tests.
"""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from engines.daily_ca.models import DailyCaArticle


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_article(**kwargs) -> MagicMock:
    """Build a minimal MagicMock that looks like a DailyCaArticle instance."""
    article = MagicMock(spec=DailyCaArticle)
    article.id = uuid.uuid4()
    article.title = kwargs.get("title", "Test Article Title")
    article.news_context = kwargs.get("news_context", "Some news context here.")
    article.is_published = kwargs.get("is_published", True)
    article.slug = kwargs.get("slug", "2026-04-10-test-article")
    return article


# ── on_daily_ca_article_save ──────────────────────────────────────────────────


class TestOnDailyCaArticleSave:
    """Unit tests for the post_save signal handler."""

    def test_thread_started_when_published(self):
        """Thread must be started when is_published=True and text is non-empty."""
        from engines.daily_ca.signals import on_daily_ca_article_save

        article = _make_article(is_published=True)

        with patch("engines.daily_ca.signals.threading.Thread") as mock_thread_cls:
            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread
            on_daily_ca_article_save(sender=None, instance=article)

        mock_thread_cls.assert_called_once()
        mock_thread.start.assert_called_once()

    def test_no_thread_when_not_published(self):
        """Thread must NOT be started when is_published=False."""
        from engines.daily_ca.signals import on_daily_ca_article_save

        article = _make_article(is_published=False)

        with patch("engines.daily_ca.signals.threading.Thread") as mock_thread_cls:
            on_daily_ca_article_save(sender=None, instance=article)

        mock_thread_cls.assert_not_called()

    def test_no_thread_when_text_empty(self):
        """Thread must NOT be started when title and news_context are both empty."""
        from engines.daily_ca.signals import on_daily_ca_article_save

        article = _make_article(is_published=True, title="", news_context="")

        with patch("engines.daily_ca.signals.threading.Thread") as mock_thread_cls:
            on_daily_ca_article_save(sender=None, instance=article)

        mock_thread_cls.assert_not_called()

    def test_thread_is_daemon(self):
        """Spawned thread must be a daemon (non-blocking)."""
        from engines.daily_ca.signals import on_daily_ca_article_save

        article = _make_article(is_published=True)

        with patch("engines.daily_ca.signals.threading.Thread") as mock_thread_cls:
            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread
            on_daily_ca_article_save(sender=None, instance=article)

        call_kwargs = mock_thread_cls.call_args.kwargs
        assert call_kwargs.get("daemon") is True


# ── _generate_and_save_embedding ──────────────────────────────────────────────


@pytest.mark.django_db
class TestGenerateAndSaveEmbedding:
    """Integration-style unit tests for the background worker."""

    def test_skips_if_embedding_already_exists(self):
        """Worker must skip EmbeddingService if embedding already in DB."""
        from engines.content.models import Embedding
        from engines.daily_ca.signals import _generate_and_save_embedding

        article = DailyCaArticle.objects.create(
            title="Signal Test Article",
            slug=f"2026-04-22-signal-test-{uuid.uuid4().hex[:6]}",
            published_date=date(2026, 4, 22),
            body_md="Some content.",
        )
        # Pre-create an embedding to simulate already embedded
        Embedding.objects.create(
            content_type="daily_ca_article",
            content_id=article.id,
            vector=[0.1] * 384,
            model_name="all-MiniLM-L6-v2",
        )

        with patch(
            "engines.content.services.embedding_service.EmbeddingService.generate_embedding"
        ) as mock_gen:
            _generate_and_save_embedding(str(article.id), "Test title context")

        mock_gen.assert_not_called()

    def test_creates_embedding_when_missing(self):
        """Worker must create an Embedding record when none exists."""
        from engines.content.models import Embedding
        from engines.daily_ca.signals import _generate_and_save_embedding

        article = DailyCaArticle.objects.create(
            title="New Signal Article",
            slug=f"2026-04-22-new-signal-{uuid.uuid4().hex[:6]}",
            published_date=date(2026, 4, 22),
            body_md="Some content.",
        )

        with patch(
            "engines.content.services.embedding_service.EmbeddingService.generate_embedding",
            return_value=[0.5] * 384,
        ):
            _generate_and_save_embedding(str(article.id), "New Signal Article context")

        assert Embedding.objects.filter(
            content_type="daily_ca_article", content_id=article.id
        ).exists()

    def test_swallows_exceptions_never_raises(self):
        """Worker must catch all exceptions and never propagate them."""
        from engines.daily_ca.signals import _generate_and_save_embedding

        with patch(
            "engines.content.services.embedding_service.EmbeddingService.generate_embedding",
            side_effect=RuntimeError("HF API down"),
        ):
            # Must not raise
            _generate_and_save_embedding(str(uuid.uuid4()), "Some text")
