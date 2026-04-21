"""
engines/daily_ca/tests/test_apps.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tests for the startup backfill logic in engines/daily_ca/apps.py.

EmbeddingService and DailyCaArticle are imported INSIDE _startup_backfill
(lazy imports), so they must be patched at their actual import locations,
not as attributes of the apps module.
"""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import patch

import pytest

from engines.daily_ca.models import DailyCaArticle

_EMB_BATCH = "engines.content.services.embedding_service.EmbeddingService.generate_embeddings_batch"


def _make_article(published: bool = True, **kwargs) -> DailyCaArticle:
    return DailyCaArticle.objects.create(
        title=kwargs.get("title", "Backfill Test Article"),
        slug=kwargs.get("slug", f"2026-04-22-backfill-{uuid.uuid4().hex[:6]}"),
        published_date=kwargs.get("published_date", date(2026, 4, 22)),
        body_md="Some content.",
        is_published=published,
    )


class TestIsPytestRunning:
    """Unit tests for _is_running_under_pytest() detection logic."""

    def test_returns_true_under_pytest(self):
        """When called from within a pytest process, must return True."""
        from engines.daily_ca.apps import _is_running_under_pytest

        assert _is_running_under_pytest() is True

    def test_xdist_worker_env_var_triggers_true(self):
        """PYTEST_XDIST_WORKER env var alone must return True (xdist worker detection)."""
        import os
        from unittest.mock import patch
        from engines.daily_ca.apps import _is_running_under_pytest

        with patch.dict(os.environ, {"PYTEST_XDIST_WORKER": "gw0"}):
            result = _is_running_under_pytest()

        assert result is True

    def test_pytest_current_test_env_var_triggers_true(self):
        """PYTEST_CURRENT_TEST env var alone must return True."""
        import os
        from unittest.mock import patch
        from engines.daily_ca.apps import _is_running_under_pytest

        with patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "test_foo::bar"}):
            result = _is_running_under_pytest()

        assert result is True


@pytest.mark.django_db
class TestStartupBackfill:
    def test_early_exit_when_no_published_articles(self):
        """No published articles → EmbeddingService never called."""
        from engines.daily_ca.apps import _startup_backfill

        DailyCaArticle.objects.filter(is_published=True).delete()

        with patch(_EMB_BATCH) as mock_batch:
            _startup_backfill()

        mock_batch.assert_not_called()

    def test_early_exit_when_all_already_embedded(self):
        """All published articles already have embeddings → no batch call."""
        from engines.content.models import Embedding
        from engines.daily_ca.apps import _startup_backfill

        article = _make_article(published=True)
        Embedding.objects.create(
            content_type="daily_ca_article",
            content_id=article.id,
            vector=[0.1] * 384,
            model_name="all-MiniLM-L6-v2",
        )

        with patch(_EMB_BATCH) as mock_batch:
            _startup_backfill()

        mock_batch.assert_not_called()

    def test_calls_batch_for_missing_articles(self):
        """Articles without embeddings → generate_embeddings_batch called once."""
        from engines.daily_ca.apps import _startup_backfill

        _make_article(published=True, title="Missing 1")
        _make_article(published=True, title="Missing 2")

        with patch(_EMB_BATCH, return_value=[[0.5] * 384, [0.5] * 384]) as mock_batch:
            _startup_backfill()

        mock_batch.assert_called_once()

    def test_creates_embedding_records_for_missing(self):
        """Embedding objects are created in the DB for articles missing embeddings."""
        from engines.content.models import Embedding
        from engines.daily_ca.apps import _startup_backfill

        article = _make_article(published=True, title="Should Get Embedded")

        with patch(_EMB_BATCH, return_value=[[0.3] * 384]):
            _startup_backfill()

        assert Embedding.objects.filter(
            content_type="daily_ca_article", content_id=article.id
        ).exists()

    def test_unpublished_articles_never_embedded(self):
        """Unpublished drafts must never get embedded."""
        from engines.content.models import Embedding
        from engines.daily_ca.apps import _startup_backfill

        draft = _make_article(published=False, title="Draft Article")

        with patch(_EMB_BATCH, return_value=[]) as mock_batch:
            _startup_backfill()

        mock_batch.assert_not_called()
        assert not Embedding.objects.filter(
            content_type="daily_ca_article", content_id=draft.id
        ).exists()

    def test_batch_exception_does_not_raise(self):
        """A batch failure must be caught — backfill must not propagate exceptions."""
        from engines.daily_ca.apps import _startup_backfill

        _make_article(published=True, title="Batch Fail Article")

        with patch(_EMB_BATCH, side_effect=RuntimeError("HF API down")):
            _startup_backfill()  # must not raise

    def test_top_level_exception_never_raises(self):
        """Even if DB queries fail, _startup_backfill must not crash Django startup."""
        from engines.daily_ca.apps import _startup_backfill

        with patch(
            "engines.daily_ca.models.DailyCaArticle.objects.filter",
            side_effect=Exception("DB gone"),
        ):
            _startup_backfill()  # must not raise
