"""
Management command to cleanup expired CA chunks

Usage:
    python manage.py cleanup_expired
"""

from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from engines.content.services.embedding_service import EmbeddingService
from engines.current_affairs.models import CAChunk


class Command(BaseCommand):
    help = "Mark expired CA chunks and optionally delete them"

    def add_arguments(self, parser) -> Any:  # type: ignore
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Actually delete expired chunks (instead of just marking)",
        )

    def handle(self, *args, **options) -> Any:  # type: ignore
        delete_expired = options["delete"]

        # Find expired chunks
        now = timezone.now()
        expired_chunks = CAChunk.objects.filter(expiry_date__lt=now, is_expired=False)

        count = expired_chunks.count()

        if delete_expired:
            # THE LEAK FIX (FEATURES_SUPABASE_CLEANUP.md S6).
            # content_embedding.content_id is a plain UUID with NO foreign key, so
            # deleting a chunk does NOT cascade to its embedding. Capture the ids
            # first, then delete the chunks AND their embeddings in one transaction.
            # Skipping the second delete is exactly what orphaned 196,937 vectors.
            db_alias = expired_chunks.db
            expired_ids = [
                str(cid) for cid in expired_chunks.values_list("id", flat=True)
            ]

            with transaction.atomic(using=db_alias):
                expired_chunks.delete()
                emb_deleted = EmbeddingService.delete_embeddings_for(
                    "ca_chunk", expired_ids, using=db_alias
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Deleted {count} expired CA chunks "
                    f"+ {emb_deleted} matching embeddings"
                )
            )
        else:
            # Mark as expired
            expired_chunks.update(is_expired=True)
            self.stdout.write(
                self.style.SUCCESS(f"✓ Marked {count} CA chunks as expired")
            )

        # Show stats
        total_chunks = CAChunk.objects.count()
        active_chunks = CAChunk.objects.filter(is_expired=False).count()

        self.stdout.write(f"Total CA chunks: {total_chunks}")
        self.stdout.write(f"Active chunks: {active_chunks}")
