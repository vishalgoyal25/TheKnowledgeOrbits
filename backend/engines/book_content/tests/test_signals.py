"""
engines/book_content/tests/test_signals.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tests for engines/book_content/signals.py (P3.4 — Redis cache invalidation).

Covers:
  - _bust_subject_caches: deletes tree key and graph key for given subject_id
  - on_topic_save: busts cache when subject_id is present
  - on_topic_save: skips cache bust when subject_id is None
  - on_book_content_save: busts cache via topic.subject_id
  - on_book_content_save: swallows exceptions (no topic or no subject_id)

All Django cache calls are mocked — no Redis required in tests.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch


# ── _bust_subject_caches ──────────────────────────────────────────────────────


class TestBustSubjectCaches:
    """Unit tests for _bust_subject_caches — pure cache key deletion."""

    def test_deletes_tree_and_graph_keys(self):
        """Both tree and graph cache keys must be deleted for the given subject_id."""
        from engines.book_content.signals import _bust_subject_caches

        subject_id = str(uuid.uuid4())

        with patch("engines.book_content.signals.cache") as mock_cache:
            _bust_subject_caches(subject_id)

        expected_tree_key = f"book_subject_tree_{subject_id}_v1"
        expected_graph_key = f"book_subject_graph_{subject_id}_v1"

        deleted_keys = [c.args[0] for c in mock_cache.delete.call_args_list]
        assert expected_tree_key in deleted_keys
        assert expected_graph_key in deleted_keys

    def test_calls_delete_exactly_twice(self):
        """Exactly two cache.delete calls — one for tree, one for graph."""
        from engines.book_content.signals import _bust_subject_caches

        with patch("engines.book_content.signals.cache") as mock_cache:
            _bust_subject_caches(str(uuid.uuid4()))

        assert mock_cache.delete.call_count == 2


# ── on_topic_save ─────────────────────────────────────────────────────────────


class TestOnTopicSave:
    """Unit tests for the post_save signal on knowledge.Topic."""

    def test_busts_cache_when_subject_id_present(self):
        """Cache bust fires when the topic has a subject_id."""
        from engines.book_content.signals import on_topic_save

        subject_id = uuid.uuid4()
        instance = MagicMock()
        instance.subject_id = subject_id

        with patch("engines.book_content.signals._bust_subject_caches") as mock_bust:
            on_topic_save(sender=None, instance=instance)

        mock_bust.assert_called_once_with(str(subject_id))

    def test_skips_bust_when_no_subject_id(self):
        """No subject_id → _bust_subject_caches must NOT be called."""
        from engines.book_content.signals import on_topic_save

        instance = MagicMock()
        instance.subject_id = None

        with patch("engines.book_content.signals._bust_subject_caches") as mock_bust:
            on_topic_save(sender=None, instance=instance)

        mock_bust.assert_not_called()


# ── on_book_content_save ──────────────────────────────────────────────────────


class TestOnBookContentSave:
    """Unit tests for the post_save signal on book_content.BookContent."""

    def test_busts_cache_via_topic_subject_id(self):
        """Cache bust fires using instance.topic.subject_id."""
        from engines.book_content.signals import on_book_content_save

        subject_id = uuid.uuid4()
        instance = MagicMock()
        instance.topic.subject_id = subject_id

        with patch("engines.book_content.signals._bust_subject_caches") as mock_bust:
            on_book_content_save(sender=None, instance=instance)

        mock_bust.assert_called_once_with(str(subject_id))

    def test_swallows_exception_when_topic_is_none(self):
        """If instance.topic raises AttributeError, must not propagate."""
        from engines.book_content.signals import on_book_content_save

        class _NoTopic:
            @property
            def topic(self):
                raise AttributeError("no topic")

        with patch("engines.book_content.signals._bust_subject_caches") as mock_bust:
            # Must not raise
            on_book_content_save(sender=None, instance=_NoTopic())

        mock_bust.assert_not_called()
