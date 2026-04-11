"""
engines/daily_ca/management/commands/cleanup_raw_ca.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase K2 — cleanup_raw_ca management command.

Deletes raw CA ingestion data older than N months to reclaim DB space.
Raw CA data (ca_article, ca_chunk, ca_topic_link) is ephemeral — it was
used to generate Daily CA articles and is no longer needed after that.

SAFE: All generated content assets are KEPT FOREVER — never touched.

Usage:
    python manage.py cleanup_raw_ca --months-old 1            # dry-run (default)
    python manage.py cleanup_raw_ca --months-old 1 --confirm  # actually deletes
    python manage.py cleanup_raw_ca --months-old 3 --database=supabase --confirm

What gets DELETED (ephemeral ingestion data):
    ca_article     — raw scraped articles from The Hindu / IndianExpress
    ca_chunk       — chunked text segments of those articles
    ca_topic_link  — topic-linking records for those chunks

What is KEPT FOREVER (permanent generated assets):
    daily_ca_article       — our generated CA articles
    daily_ca_proposal      — proposal audit records
    daily_ca_static_link   — article ↔ static content links
    tag                    — keyword tag definitions
    article_tag            — tag ↔ article links
    concept_page           — concept page stubs + full pages
    concept_article_link   — concept ↔ article links

Safety rules:
    — Requires --confirm flag to perform actual deletion (default = dry-run)
    — Minimum --months-old is 1 (refuse to delete data < 1 month old)
    — Prints row counts and estimated space BEFORE deleting
    — Deletion order respects FK constraints: ca_topic_link → ca_chunk → ca_article
"""

from datetime import timedelta

import sentry_sdk
import structlog
from django.core.management.base import BaseCommand
from django.utils import timezone

from engines.current_affairs.models import CAArticle, CAChunk, CATopicLink

logger = structlog.get_logger(__name__)

# Average bytes per row (rough estimates for space calculation display)
_BYTES_PER_CA_ARTICLE = 4_000
_BYTES_PER_CA_CHUNK = 1_500
_BYTES_PER_CA_TOPIC_LINK = 200


class Command(BaseCommand):
    help = (
        "Delete raw CA ingestion data (ca_article, ca_chunk, ca_topic_link) "
        "older than N months. Add --confirm to actually delete (default: dry-run)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--months-old",
            type=int,
            default=1,
            help="Delete rows older than this many months (minimum 1, default 1).",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            default=False,
            help="Actually perform deletion. Without this flag, runs as dry-run only.",
        )
        parser.add_argument(
            "--database",
            default="default",
            help="Database alias to use (default: 'default'). Use 'supabase' for production.",
        )

    def handle(self, *args, **options):
        months_old: int = options["months_old"]
        confirm: bool = options["confirm"]
        db_alias: str = options["database"]

        # ── Safety: refuse months_old < 1 ────────────────────────────────────
        if months_old < 1:
            self.stderr.write(
                self.style.ERROR(
                    "--months-old must be at least 1. "
                    "Refusing to delete data less than 1 month old."
                )
            )
            return

        cutoff = timezone.now() - timedelta(days=months_old * 30)
        mode_label = "DRY RUN" if not confirm else "LIVE DELETE"

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\n{'━' * 60}\n"
                f"  CA Cleanup — {mode_label}\n"
                f"  Database  : {db_alias}\n"
                f"  Cutoff    : older than {months_old} month(s) "
                f"(before {cutoff.strftime('%Y-%m-%d %H:%M')})\n"
                f"{'━' * 60}"
            )
        )

        # ── Count rows to be deleted ──────────────────────────────────────────
        old_articles = CAArticle.objects.using(db_alias).filter(published_at__lt=cutoff)
        old_article_ids = list(old_articles.values_list("id", flat=True))

        count_topic_links = (
            CATopicLink.objects.using(db_alias)
            .filter(ca_chunk__ca_article_id__in=old_article_ids)
            .count()
        )

        count_chunks = (
            CAChunk.objects.using(db_alias)
            .filter(ca_article_id__in=old_article_ids)
            .count()
        )

        count_articles = len(old_article_ids)

        # ── Space estimate ────────────────────────────────────────────────────
        est_bytes = (
            count_articles * _BYTES_PER_CA_ARTICLE
            + count_chunks * _BYTES_PER_CA_CHUNK
            + count_topic_links * _BYTES_PER_CA_TOPIC_LINK
        )
        est_mb = est_bytes / (1024 * 1024)

        # ── Print counts ──────────────────────────────────────────────────────
        self.stdout.write("\n  Rows to be deleted:\n")
        self.stdout.write(f"    ca_topic_link  : {count_topic_links:,}")
        self.stdout.write(f"    ca_chunk       : {count_chunks:,}")
        self.stdout.write(f"    ca_article     : {count_articles:,}")
        self.stdout.write(f"\n  Estimated space to reclaim: ~{est_mb:.1f} MB\n")

        # ── Permanent assets — never touched ──────────────────────────────────
        self.stdout.write("  Permanent assets (NEVER deleted):")
        self.stdout.write(
            "    daily_ca_article, daily_ca_proposal, daily_ca_static_link"
        )
        self.stdout.write("    tag, article_tag, concept_page, concept_article_link\n")

        if count_articles == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Nothing to delete — no ca_article rows older than "
                    f"{months_old} month(s) found.\n"
                )
            )
            return

        # ── Dry-run exit ──────────────────────────────────────────────────────
        if not confirm:
            self.stdout.write(
                self.style.WARNING(
                    f"  DRY RUN — nothing deleted.\n"
                    f"  Re-run with --confirm to actually delete {count_articles:,} articles "
                    f"and their chunks/links.\n"
                )
            )
            self.stdout.write(self.style.MIGRATE_HEADING(f"{'━' * 60}\n"))
            return

        # ── Live deletion (FK-safe order) ─────────────────────────────────────
        self.stdout.write(
            self.style.WARNING(
                f"  Deleting {count_articles:,} articles and related rows..."
            )
        )

        try:
            # Step 1: ca_topic_link (references ca_chunk)
            deleted_links, _ = (
                CATopicLink.objects.using(db_alias)
                .filter(ca_chunk__ca_article_id__in=old_article_ids)
                .delete()
            )

            # Step 2: ca_chunk (references ca_article)
            deleted_chunks, _ = (
                CAChunk.objects.using(db_alias)
                .filter(ca_article_id__in=old_article_ids)
                .delete()
            )

            # Step 3: ca_article (filter by ID list built above — not date again)
            deleted_articles, _ = (
                CAArticle.objects.using(db_alias)
                .filter(id__in=old_article_ids)
                .delete()
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"\n  Deleted:\n"
                    f"    ca_topic_link  : {deleted_links:,}\n"
                    f"    ca_chunk       : {deleted_chunks:,}\n"
                    f"    ca_article     : {deleted_articles:,}\n"
                    f"\n  Estimated space reclaimed: ~{est_mb:.1f} MB"
                )
            )

            logger.info(
                "cleanup_raw_ca_complete",
                db_alias=db_alias,
                months_old=months_old,
                cutoff=str(cutoff.date()),
                deleted_articles=deleted_articles,
                deleted_chunks=deleted_chunks,
                deleted_topic_links=deleted_links,
                est_mb=round(est_mb, 1),
            )

        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error("cleanup_raw_ca_failed", error=str(exc))
            self.stderr.write(self.style.ERROR(f"\n  Deletion failed: {exc}"))
            return

        self.stdout.write(self.style.MIGRATE_HEADING(f"\n{'━' * 60}\n"))
