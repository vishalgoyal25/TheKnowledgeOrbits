"""
engines/book_content/management/commands/inspect_retrieval.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 6 — Read-only diagnostic for the RAG grounding gateway.

Proves cross-subject correctness ON DEMAND: given a seed topic (or raw query),
it prints the retrieved chunks with their subject / topic / relevance score, so
you can SEE that retrieval follows *relevance* across subjects (e.g. a Budget
topic surfacing Economy + Polity + Governance) and stops at the noise floor
(no out-of-context matches). This is the live demo tool for interviews.

No LLM calls. Embedding (HF) is called once to embed the query.

Usage:
  python manage.py inspect_retrieval --subject "Indian Polity & Constitution" --db supabase
  python manage.py inspect_retrieval --topic-id <uuid> --db supabase
  python manage.py inspect_retrieval --query "Union Budget" --db supabase
  python manage.py inspect_retrieval --subject "Environment & Ecology" --k-book 6 --k-ca 4 --db supabase
"""

from collections import Counter

import structlog
from django.core.management.base import BaseCommand, CommandError

from engines.book_content.services.retrieval_service import retrieve_grounding

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Inspect RAG grounding gateway output for a seed topic (read-only, no LLM)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--topic-id",
            type=str,
            default=None,
            help="knowledge.Topic UUID to seed from.",
        )
        parser.add_argument(
            "--subject",
            type=str,
            default=None,
            help="Use the first BookContent topic under this subject as the seed.",
        )
        parser.add_argument(
            "--query",
            type=str,
            default=None,
            help="Explicit query text (combined with the seed topic's own text).",
        )
        parser.add_argument(
            "--db",
            dest="db_alias",
            type=str,
            default="default",
            help="DB alias: default | supabase (default: default).",
        )
        parser.add_argument(
            "--k-book", type=int, default=6, help="Max theory (book) chunks."
        )
        parser.add_argument(
            "--k-ca", type=int, default=4, help="Max recency (CA) chunks."
        )

    def handle(self, *args, **opts):
        db_alias = opts["db_alias"]
        topic_id = opts["topic_id"]
        subject = opts["subject"]
        query = opts["query"]
        k_book = opts["k_book"]
        k_ca = opts["k_ca"]

        seed_name = None

        # Resolve a seed topic from --subject if no explicit topic-id given.
        if not topic_id and subject:
            from engines.book_content.models import BookContent

            bc = (
                BookContent.objects.using(db_alias)
                .filter(subject__name=subject)
                .select_related("topic", "subject")
                .first()
            )
            if not bc:
                raise CommandError(
                    f"No BookContent found under subject '{subject}' in DB '{db_alias}'."
                )
            topic_id = str(bc.topic_id) if bc.topic_id else None
            seed_name = bc.topic.name if bc.topic_id else ""

        if not topic_id and not query:
            raise CommandError(
                "Provide at least one of: --topic-id, --subject, or --query."
            )

        # Resolve display name for an explicit topic-id.
        if topic_id and not seed_name:
            from engines.knowledge.models import Topic

            t = (
                Topic.objects.using(db_alias)
                .filter(id=topic_id)
                .select_related("subject")
                .first()
            )
            seed_name = t.name if t else "(unknown topic)"

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\n=== RAG GROUNDING INSPECTION (db={db_alias}) ==="
            )
        )
        self.stdout.write(f"Seed topic : {seed_name}  ({topic_id or 'no topic_id'})")
        self.stdout.write(f"Query      : {query or '(from seed topic)'}")
        self.stdout.write(f"k_book={k_book}  k_ca={k_ca}\n")

        result = retrieve_grounding(
            query=query,
            seed_topic_id=topic_id,
            k_book=k_book,
            k_ca=k_ca,
            db_alias=db_alias,
        )

        stats = result.get("stats", {})
        self.stdout.write(
            self.style.HTTP_INFO(
                f"STATS: book_hits={stats.get('book_hits')}  ca_hits={stats.get('ca_hits')}  "
                f"graph_topics={stats.get('graph_topics')}  returned={stats.get('returned')}"
            )
        )

        chunks = result.get("chunks", [])
        if not chunks:
            self.stdout.write(
                self.style.WARNING(
                    "\nNo chunks returned (empty corpus for this seed, or all matches "
                    "below the 0.62 relevance floor)."
                )
            )
            self.stdout.write(
                "→ Graceful-fallback case: a generator would fall back to wiki here.\n"
            )
            return

        book = [c for c in chunks if c["content_type"] == "book_chunk"]
        ca = [c for c in chunks if c["content_type"] == "ca_chunk"]

        if book:
            self.stdout.write(
                self.style.MIGRATE_LABEL("\n— Retrieved THEORY (book_chunk) —")
            )
            for i, c in enumerate(book, 1):
                self.stdout.write(
                    f"  [{i}] score={c['score']:.3f}  [{c['subject']}]  {c['topic']}"
                )
                self.stdout.write(f"      {c['text'][:160].strip()}...")

        if ca:
            self.stdout.write(
                self.style.MIGRATE_LABEL("\n— Retrieved RECENCY (ca_chunk) —")
            )
            for i, c in enumerate(ca, 1):
                self.stdout.write(
                    f"  [CA{i}] score={c['score']:.3f}  [{c['subject']}]  {c['topic'][:70]}"
                )
                self.stdout.write(f"       {c['text'][:160].strip()}...")

        # The headline proof: how many distinct subjects the theory spans.
        subj_counter = Counter(c["subject"] for c in book if c.get("subject"))
        self.stdout.write(
            self.style.MIGRATE_HEADING("\n— CROSS-SUBJECT SPREAD (theory) —")
        )
        if subj_counter:
            for subj, n in subj_counter.most_common():
                self.stdout.write(f"  {n}x  {subj}")
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n[OK] Retrieval followed RELEVANCE across {len(subj_counter)} "
                    "subject(s) — related content surfaced; out-of-context filtered by "
                    "the 0.62 floor.\n"
                )
            )
        else:
            self.stdout.write("  (no book theory — recency-only grounding)\n")
