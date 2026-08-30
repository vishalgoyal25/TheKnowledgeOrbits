"""
engines/content/tests/test_embedding_cleanup.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Regression tests for EmbeddingService.delete_embeddings_for
(FEATURES_SUPABASE_CLEANUP.md S6 — the orphan-leak fix).

`content_embedding.content_id` is a plain UUID with NO foreign key, so deleting
content never cascades to its embedding. That leak grew the table to 610 MB /
232k rows (96.5% orphans) and tripped the Supabase quota. `delete_embeddings_for`
is the shared API every deletion site now calls to remove the pair together.

These are mock-based and offline: the point is to lock the query CONTRACT (right
content_type, right ids, scoped delete) so a future refactor can't silently
reintroduce the leak. Real deletion was proven live during the 2026-08-29 cleanup.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from engines.content.services.embedding_service import EmbeddingService


def _patched_embedding():
    """Patch the Embedding model as imported lazily inside the service method."""
    return patch("engines.content.models.Embedding")


class TestDeleteEmbeddingsFor:
    def test_deletes_only_the_given_type_and_ids(self) -> None:
        with _patched_embedding() as MockEmbedding:
            qs = MagicMock()
            qs.delete.return_value = (2, {"content.Embedding": 2})
            MockEmbedding.objects.using.return_value.filter.return_value = qs

            deleted = EmbeddingService.delete_embeddings_for(
                "ca_chunk", ["id-1", "id-2"]
            )

            assert deleted == 2
            MockEmbedding.objects.using.assert_called_once_with("default")
            MockEmbedding.objects.using.return_value.filter.assert_called_once_with(
                content_type="ca_chunk", content_id__in=["id-1", "id-2"]
            )
            qs.delete.assert_called_once()

    def test_empty_ids_is_a_noop_and_never_queries(self) -> None:
        with _patched_embedding() as MockEmbedding:
            deleted = EmbeddingService.delete_embeddings_for("ca_chunk", [])

            assert deleted == 0
            MockEmbedding.objects.using.assert_not_called()

    def test_uuid_ids_are_stringified(self) -> None:
        import uuid

        u1, u2 = uuid.uuid4(), uuid.uuid4()
        with _patched_embedding() as MockEmbedding:
            qs = MagicMock()
            qs.delete.return_value = (0, {})
            MockEmbedding.objects.using.return_value.filter.return_value = qs

            EmbeddingService.delete_embeddings_for("ca_chunk", [u1, u2])

            MockEmbedding.objects.using.return_value.filter.assert_called_once_with(
                content_type="ca_chunk", content_id__in=[str(u1), str(u2)]
            )

    def test_honors_the_database_alias(self) -> None:
        with _patched_embedding() as MockEmbedding:
            qs = MagicMock()
            qs.delete.return_value = (1, {"content.Embedding": 1})
            MockEmbedding.objects.using.return_value.filter.return_value = qs

            EmbeddingService.delete_embeddings_for("ca_chunk", ["x"], using="supabase")

            MockEmbedding.objects.using.assert_called_once_with("supabase")
