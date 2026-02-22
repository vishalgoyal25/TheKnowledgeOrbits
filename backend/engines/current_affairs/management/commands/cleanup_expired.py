"""
Management command to cleanup expired CA chunks

Usage:
    python manage.py cleanup_expired
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from engines.current_affairs.models import CAChunk


class Command(BaseCommand):
    help = "Mark expired CA chunks and optionally delete them"

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Actually delete expired chunks (instead of just marking)",
        )

    def handle(self, *args, **options):
        delete_expired = options["delete"]

        # Find expired chunks
        now = timezone.now()
        expired_chunks = CAChunk.objects.filter(expiry_date__lt=now, is_expired=False)

        count = expired_chunks.count()

        if delete_expired:
            # Delete
            expired_chunks.delete()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Deleted {count} expired CA chunks")
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
