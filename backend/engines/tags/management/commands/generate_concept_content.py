"""
engines/tags/management/commands/generate_concept_content.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase G (FEATURES3) — Concept Page content generation command.

Generates full encyclopaedic body_md for ConceptPage stubs where
is_content_ready=False. Ordered by usage_count DESC — most-referenced
concepts are generated first to maximise immediate reader value.

Usage:
  python manage.py generate_concept_content
      → top 20 stubs by usage_count

  python manage.py generate_concept_content --limit 10
      → top 10 stubs only

  python manage.py generate_concept_content --slug clnda
      → one specific concept (admin override; bypasses is_content_ready lock)

  python manage.py generate_concept_content --database=supabase
      → run against Supabase (production DB)

  python manage.py generate_concept_content --limit 5 --database=supabase
      → top 5 by usage_count on production

Process:
  1. Query ConceptPage WHERE is_content_ready=False ORDER BY usage_count DESC LIMIT N
     (--slug mode: fetch by slug regardless of is_content_ready)
  2. For each concept: call ConceptContentService.generate_concept_content()
  3. GROQ rate limit sleep (12s) is handled inside llm_call() — no extra sleep here
  4. Per-concept stdout: "✓ slug (N words)" or "✗ slug — skipped/failed"
  5. On exception: log to Sentry + structlog, continue loop (never abort batch)
  6. Final summary line: "Generated X / Y | GROQ calls: Z"

Notes:
  - is_content_ready=True concepts are skipped automatically (idempotent)
  - Re-running always picks the next batch of stubs ordered by usage_count
  - --slug bypasses the is_content_ready lock for admin refresh of a single concept
  - All DB access uses the selected db_alias (default: 'default')
"""

import structlog
from django.core.management.base import BaseCommand, CommandError

import sentry_sdk

from engines.tags.models import ConceptPage
from engines.tags.services.concept_content_service import ConceptContentService

logger = structlog.get_logger(__name__)

# Default session cap — keeps a single run predictable and within GROQ limits
DEFAULT_LIMIT = 20


class Command(BaseCommand):
    help = (
        "Generate full encyclopaedic body_md for ConceptPage stubs. "
        "Targets is_content_ready=False, ordered by usage_count DESC."
    )

    # ── Argument declaration ──────────────────────────────────────────────────

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=DEFAULT_LIMIT,
            metavar="N",
            help=(
                f"Maximum number of concepts to generate in this run "
                f"(default: {DEFAULT_LIMIT}). Ignored when --slug is used."
            ),
        )
        parser.add_argument(
            "--slug",
            type=str,
            default=None,
            metavar="SLUG",
            help=(
                "Generate content for ONE specific concept by slug. "
                "Bypasses is_content_ready lock — for admin refresh only."
            ),
        )
        parser.add_argument(
            "--database",
            type=str,
            default="default",
            metavar="DB_ALIAS",
            help="Django DB alias to use (default: 'default'). Use 'supabase' for production.",
        )

    # ── Entry point ───────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        db_alias: str = options["database"]
        limit: int = options["limit"]
        target_slug: str | None = options["slug"]

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\n{'━' * 60}\n"
                f"  Concept Page Content Generator\n"
                f"  DB: {db_alias}"
                + (
                    f"  |  Target slug: {target_slug}"
                    if target_slug
                    else f"  |  Limit: {limit}"
                )
                + f"\n{'━' * 60}"
            )
        )

        # ── Fetch target concepts ─────────────────────────────────────────────

        if target_slug:
            concepts = self._fetch_by_slug(target_slug, db_alias)
        else:
            concepts = self._fetch_batch(limit, db_alias)

        if not concepts:
            self.stdout.write(
                self.style.WARNING(
                    "  No concepts found matching the criteria. Nothing to generate."
                )
            )
            return

        total = len(concepts)
        self.stdout.write(f"  Found {total} concept(s) to process.\n")

        # ── Generation loop ───────────────────────────────────────────────────

        generated = 0
        skipped = 0
        failed = 0

        for idx, concept in enumerate(concepts, start=1):
            prefix = f"  [{idx:>3}/{total}]"
            self.stdout.write(f"{prefix} {concept.slug} ... ", ending="")

            try:
                # force=True only when --slug is explicitly passed (admin override)
                success = ConceptContentService.generate_concept_content(
                    concept=concept,
                    db_alias=db_alias,
                    force=bool(target_slug),
                )
            except Exception as exc:
                # Never abort the batch — log and continue
                sentry_sdk.capture_exception(exc)
                logger.error(
                    "generate_concept_content_loop_error",
                    slug=concept.slug,
                    error=str(exc),
                )
                self.stdout.write(self.style.ERROR(f"ERROR — {exc}"))
                failed += 1
                continue

            if success:
                # Re-fetch to get accurate word count from saved body
                try:
                    concept.refresh_from_db(fields=["body_md"])
                    word_count = len(concept.body_md.split())
                except Exception:
                    word_count = 0

                self.stdout.write(self.style.SUCCESS(f"✓  ({word_count} words)"))
                generated += 1
            else:
                # Skipped = already is_content_ready=True and force=False
                self.stdout.write(self.style.WARNING("skipped (already ready)"))
                skipped += 1

        # ── Summary ───────────────────────────────────────────────────────────

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\n{'─' * 60}\n"
                f"  Generated : {generated}\n"
                f"  Skipped   : {skipped}\n"
                f"  Failed    : {failed}\n"
                f"  GROQ calls: {generated}  (1 per generated concept)\n"
                f"{'─' * 60}\n"
            )
        )

        logger.info(
            "generate_concept_content_complete",
            db_alias=db_alias,
            generated=generated,
            skipped=skipped,
            failed=failed,
            total=total,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _fetch_batch(self, limit: int, db_alias: str) -> list[ConceptPage]:
        """
        Fetch up to `limit` ConceptPage stubs not yet content-ready,
        ordered by usage_count DESC (most-referenced first).
        """
        try:
            return list(
                ConceptPage.objects.using(db_alias)
                .filter(is_content_ready=False)
                .order_by("-usage_count", "name")[:limit]
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error(
                "generate_concept_content_fetch_failed",
                db_alias=db_alias,
                error=str(exc),
            )
            raise CommandError(
                f"Failed to fetch ConceptPage stubs from DB '{db_alias}': {exc}"
            ) from exc

    def _fetch_by_slug(self, slug: str, db_alias: str) -> list[ConceptPage]:
        """
        Fetch a single ConceptPage by slug for admin override.
        Raises CommandError if not found.
        """
        try:
            concept = ConceptPage.objects.using(db_alias).get(slug=slug)
            return [concept]
        except ConceptPage.DoesNotExist:
            raise CommandError(
                f"ConceptPage with slug '{slug}' not found in DB '{db_alias}'."
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error(
                "generate_concept_content_slug_fetch_failed",
                slug=slug,
                db_alias=db_alias,
                error=str(exc),
            )
            raise CommandError(
                f"Error fetching ConceptPage '{slug}' from DB '{db_alias}': {exc}"
            ) from exc
