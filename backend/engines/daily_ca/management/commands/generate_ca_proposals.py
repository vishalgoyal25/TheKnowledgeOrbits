"""
engines/daily_ca/management/commands/generate_ca_proposals.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase F2 — generate_ca_proposals management command.

Fetches yesterday's completed CAArticles, scores them for UPSC relevance,
groups by knowledge topic (deduplicates sources), and generates
CaDailyProposal records via one lightweight GROQ call per topic.

Usage:
    python manage.py generate_ca_proposals                  # defaults to today's date
    python manage.py generate_ca_proposals --date today
    python manage.py generate_ca_proposals --date 2026-04-10
    python manage.py generate_ca_proposals --database=supabase
    python manage.py generate_ca_proposals --dry-run        # preview without DB writes

Process per run:
  1. Fetch CAArticles published in last 24hrs with processing_status='completed'
  2. Score each with RelevanceScorerService (threshold >= 5.0)
  3. Walk chunks → CATopicLink → group by Topic (deduplicate)
  4. Top 30 topic groups max — sorted by combined relevance
  5. Per topic group: collect top 3 chunks, 1 GROQ call → title + description + gs_paper
  6. Save CaDailyProposal (skip if already exists for same date + topic)
  7. Session cap: 30 GROQ calls max (safety valve)

Session cap: if 30 GROQ calls consumed before all topics are processed,
             remaining topics are skipped and logged as warnings.
             Re-run the command the next day — proposals are idempotent.
"""

import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta

import sentry_sdk
import structlog
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from engines.book_content.services.llm_service import llm_call
from engines.current_affairs.models import CAArticle, CAChunk
from engines.current_affairs.services.relevance_scorer import RelevanceScorerService
from engines.daily_ca.models import CaDailyProposal

logger = structlog.get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_TOPICS_PER_RUN = 30  # Hard cap on proposals generated per run
MAX_GROQ_CALLS = 30  # Session safety cap
TOP_CHUNKS_PER_TOPIC = 3  # How many source chunks to collect per proposal
RELEVANCE_THRESHOLD = 5.0  # Minimum score from RelevanceScorerService

# ── GS Paper mapping by UPSC subject name ────────────────────────────────────
# Used as fallback when LLM doesn't return a valid gs_paper value.
SUBJECT_TO_GS: dict[str, str] = {
    "indian heritage and culture": "GS1",
    "history": "GS1",
    "modern history": "GS1",
    "world history": "GS1",
    "indian society": "GS1",
    "social issues": "GS1",
    "geography": "GS1",
    "physical geography": "GS1",
    "indian geography": "GS1",
    "indian polity": "GS2",
    "polity": "GS2",
    "governance": "GS2",
    "social justice": "GS2",
    "international relations": "GS2",
    "indian economy": "GS3",
    "economy": "GS3",
    "agriculture": "GS3",
    "science and technology": "GS3",
    "science & technology": "GS3",
    "environment": "GS3",
    "ecology": "GS3",
    "internal security": "GS3",
    "security": "GS3",
    "disaster management": "GS3",
    "ethics": "GS4",
    "integrity": "GS4",
}

# ── GROQ Prompt ───────────────────────────────────────────────────────────────
_PROPOSAL_PROMPT = """You are a UPSC Current Affairs editor.

Based on the news excerpts below about "{topic_name}", write a daily CA proposal.

News excerpts:
{news_text}

Return ONLY valid JSON (no markdown fences, no extra text):
{{
  "title": "A sharp, specific 10-15 word article title for UPSC aspirants",
  "description": "Sentence 1: What happened in the news. Sentence 2: Why this matters for UPSC. Sentence 3: Key fact or figure a student must know.",
  "gs_paper": "GS1 or GS2 or GS3 or GS4"
}}"""


class Command(BaseCommand):
    help = (
        "Phase F2: Generate CaDailyProposal records from yesterday's CA articles. "
        "Scores for UPSC relevance, groups by topic, creates one proposal per topic."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            default="today",
            help=(
                "Target date for proposals. "
                "'today' (default) or YYYY-MM-DD. "
                "Proposals are created for this date."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview how many proposals would be created without writing to DB.",
        )
        parser.add_argument(
            "--database",
            default="default",
            help="Database alias to use (e.g. 'default' or 'supabase').",
        )

    # ── Main handler ──────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        db_alias: str = options["database"]
        target_date: date = self._parse_date(options["date"])

        self.stdout.write(
            self.style.WARNING(
                f"{'[DRY Run] ' if dry_run else ''}"
                f"Generating CA proposals for {target_date} → database: {db_alias}"
            )
        )

        # Step 1: Fetch completed articles published in last 24 hrs
        articles = self._fetch_recent_articles(db_alias)
        self.stdout.write(f"  → {len(articles)} completed articles in last 24hrs")

        if not articles:
            self.stdout.write(self.style.WARNING("No articles found. Exiting."))
            return

        # Step 2: Score and filter for UPSC relevance
        relevant = self._score_and_filter(articles)
        self.stdout.write(
            f"  → {len(relevant)} articles passed relevance threshold ({RELEVANCE_THRESHOLD})"
        )

        if not relevant:
            self.stdout.write(
                self.style.WARNING("No relevant articles found. Exiting.")
            )
            return

        # Step 3: Group by knowledge topic
        topic_groups = self._group_by_topic(relevant, db_alias)
        self.stdout.write(f"  → {len(topic_groups)} unique topics identified")

        if not topic_groups:
            self.stdout.write(self.style.WARNING("No topic groups found. Exiting."))
            return

        # Step 4: Sort by combined relevance score, cap at MAX_TOPICS_PER_RUN
        sorted_groups = sorted(
            topic_groups.items(),
            key=lambda x: x[1]["combined_score"],
            reverse=True,
        )[:MAX_TOPICS_PER_RUN]

        self.stdout.write(
            f"  → Processing top {len(sorted_groups)} topic groups "
            f"(cap: {MAX_TOPICS_PER_RUN})"
        )

        # Step 5: Generate proposals
        created = 0
        skipped = 0
        failed = 0
        groq_calls = 0

        for topic_obj, group_data in sorted_groups:
            # Session cap check
            if groq_calls >= MAX_GROQ_CALLS:
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⚠ Session cap reached ({MAX_GROQ_CALLS} GROQ calls). "
                        f"Remaining topics skipped."
                    )
                )
                logger.warning(
                    "generate_proposals_session_cap_reached",
                    cap=MAX_GROQ_CALLS,
                    topics_remaining=len(sorted_groups) - created - skipped - failed,
                )
                break

            try:
                result = self._process_topic_group(
                    topic=topic_obj,
                    group_data=group_data,
                    target_date=target_date,
                    dry_run=dry_run,
                    db_alias=db_alias,
                )
                groq_calls += 1

                if result == "created":
                    created += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"  ✓ [{created}] {topic_obj.name[:60]}")
                    )
                elif result == "skipped":
                    skipped += 1
                    self.stdout.write(
                        f"  ~ [skip] {topic_obj.name[:60]} (already exists)"
                    )
                elif result == "dry_run":
                    created += 1
                    self.stdout.write(f"  [dry] {topic_obj.name[:60]}")

            except Exception as exc:
                failed += 1
                sentry_sdk.capture_exception(exc)
                logger.error(
                    "generate_proposals_topic_failed",
                    topic=topic_obj.name if topic_obj else "unknown",
                    error=str(exc)[:200],
                )
                self.stdout.write(
                    self.style.ERROR(f"  ✗ FAILED: {topic_obj.name[:60]} — {exc}")
                )

        # Final summary
        summary = (
            f"\n{'[DRY RUN] ' if dry_run else ''}Proposals for {target_date}: "
            f"created={created} | skipped={skipped} | failed={failed} | "
            f"groq_calls={groq_calls}"
        )
        self.stdout.write(self.style.SUCCESS(summary))
        logger.info(
            "generate_proposals_complete",
            date=str(target_date),
            created=created,
            skipped=skipped,
            failed=failed,
            groq_calls=groq_calls,
            dry_run=dry_run,
            database=db_alias,
        )

    # ── Step helpers ──────────────────────────────────────────────────────────

    def _fetch_recent_articles(self, db_alias: str) -> list[CAArticle]:
        """Fetch CAArticles published in the last 24 hours with processing_status='completed'."""
        cutoff = timezone.now() - timedelta(hours=24)
        return list(
            CAArticle.objects.using(db_alias)
            .filter(
                published_at__gte=cutoff,
                processing_status="completed",
            )
            .select_related("source")
        )

    def _score_and_filter(
        self, articles: list[CAArticle]
    ) -> list[tuple[CAArticle, float]]:
        """
        Score each article and return (article, score) tuples above threshold.
        Sorted by score descending.
        """
        scored = []
        for article in articles:
            score = RelevanceScorerService.score_article(article)
            if score >= RELEVANCE_THRESHOLD:
                scored.append((article, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def _group_by_topic(
        self, relevant: list[tuple[CAArticle, float]], db_alias: str
    ) -> dict:
        """
        Walk relevant articles → their chunks → CATopicLink → Topic.
        Groups data by topic. Returns:
        {
            Topic: {
                "combined_score": float,
                "chunks": [CAChunk, ...],       # top chunks by relevance
                "article_scores": {article_id: score},
                "source_urls": [{source_name, url, title}, ...]
            }
        }
        Deduplication: 3 news articles on same topic = 1 group, not 3 proposals.
        """
        topic_groups: dict = defaultdict(
            lambda: {
                "combined_score": 0.0,
                "chunks": [],
                "chunk_relevances": [],
                "article_scores": {},
                "source_urls": [],
                "seen_urls": set(),
            }
        )

        article_ids = [a.id for a, _ in relevant]
        article_score_map = {a.id: s for a, s in relevant}

        # Fetch all relevant chunks in one query
        chunks = (
            CAChunk.objects.using(db_alias)
            .filter(ca_article_id__in=article_ids)
            .select_related("ca_article", "ca_article__source")
            .prefetch_related("topic_links__topic__module__subject")
        )

        for chunk in chunks:
            article = chunk.ca_article
            article_score = article_score_map.get(article.id, 0.0)

            for link in chunk.topic_links.all():
                topic = link.topic
                g = topic_groups[topic]

                # Accumulate score
                g["combined_score"] += link.relevance_score + (article_score * 0.1)

                # Collect chunk (will be trimmed to top 3 later)
                g["chunks"].append(chunk)
                g["chunk_relevances"].append(link.relevance_score)

                # Track article scores
                g["article_scores"][str(article.id)] = article_score

                # Collect source URLs (deduplicated by URL)
                url = article.url
                if url not in g["seen_urls"]:
                    g["seen_urls"].add(url)
                    g["source_urls"].append(
                        {
                            "source_name": article.source.name
                            if article.source
                            else "Unknown",
                            "url": url,
                            "title": article.title,
                        }
                    )

        # Post-process: sort chunks by relevance, keep top 3
        result = {}
        for topic, g in topic_groups.items():
            if not g["chunks"]:
                continue
            # Sort chunks by their per-link relevance score
            paired = sorted(
                zip(g["chunk_relevances"], g["chunks"]),
                key=lambda x: x[0],
                reverse=True,
            )
            top_chunks = [c for _, c in paired[:TOP_CHUNKS_PER_TOPIC]]
            result[topic] = {
                "combined_score": g["combined_score"],
                "chunks": top_chunks,
                "source_urls": g["source_urls"][:5],  # cap source list
            }

        return result

    def _process_topic_group(
        self,
        topic,
        group_data: dict,
        target_date: date,
        dry_run: bool,
        db_alias: str,
    ) -> str:
        """
        For one topic group:
          - Check if proposal already exists (idempotent)
          - Build news text from top chunks
          - Call GROQ for title + description + gs_paper
          - Save CaDailyProposal

        Returns: "created" | "skipped" | "dry_run"
        """
        # Idempotency check
        exists = (
            CaDailyProposal.objects.using(db_alias)
            .filter(date=target_date, topic=topic)
            .exists()
        )
        if exists:
            return "skipped"

        # Build news text from top chunks
        chunks: list[CAChunk] = group_data["chunks"]
        news_text = "\n\n---\n\n".join(
            f"[{i+1}] {chunk.chunk_text[:600]}" for i, chunk in enumerate(chunks)
        )

        # Derive subject name from topic → module → subject
        subject_name = self._get_subject_name(topic)

        # GROQ call
        prompt = _PROPOSAL_PROMPT.format(
            topic_name=topic.name,
            news_text=news_text[:2500],
        )
        raw = llm_call(prompt, mode="standard")

        if not raw:
            raise ValueError(f"Empty GROQ response for topic: {topic.name}")

        title, description, gs_paper = self._parse_groq_response(
            raw, topic.name, subject_name
        )

        if dry_run:
            logger.info(
                "generate_proposals_dry_run",
                topic=topic.name,
                title=title,
                gs_paper=gs_paper,
                date=str(target_date),
            )
            return "dry_run"

        # Save proposal
        with transaction.atomic(using=db_alias):
            CaDailyProposal.objects.using(db_alias).create(
                date=target_date,
                title=title,
                description=description,
                topic=topic,
                subject_name=subject_name,
                gs_paper=gs_paper,
                source_urls=group_data["source_urls"],
                ca_chunk_ids=[str(c.id) for c in chunks],
                relevance_score=round(group_data["combined_score"], 2),
                status="pending",
            )

        logger.info(
            "generate_proposals_created",
            topic=topic.name,
            title=title,
            gs_paper=gs_paper,
            date=str(target_date),
            relevance_score=group_data["combined_score"],
        )
        return "created"

    # ── Utility helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _parse_date(date_str: str) -> date:
        """Parse --date argument. Accepts 'today' or YYYY-MM-DD."""
        if date_str.lower() == "today":
            return date.today()
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(
                f"Invalid date format: '{date_str}'. Use 'today' or YYYY-MM-DD."
            )

    @staticmethod
    def _get_subject_name(topic) -> str:
        """
        Safely traverse topic → module → subject → name.
        Returns empty string if the chain is broken.
        """
        try:
            return topic.module.subject.name
        except AttributeError:
            return ""

    @staticmethod
    def _parse_groq_response(
        raw: str, topic_name: str, subject_name: str
    ) -> tuple[str, str, str]:
        """
        Parse GROQ JSON response → (title, description, gs_paper).
        Falls back gracefully if JSON is malformed.
        """
        try:
            # Strip markdown fences
            cleaned = re.sub(r"```(?:json)?", "", raw).strip()
            # Extract JSON object
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if not match:
                raise ValueError("No JSON object found in GROQ response")

            data = json.loads(match.group())

            title = str(data.get("title", "")).strip()
            description = str(data.get("description", "")).strip()
            gs_paper = str(data.get("gs_paper", "")).strip().upper()

            # Validate title
            if not title:
                title = f"Daily CA: {topic_name}"

            # Validate description
            if not description:
                description = f"News update on {topic_name} — review required."

            # Validate gs_paper (must be GS1/GS2/GS3/GS4)
            if gs_paper not in {"GS1", "GS2", "GS3", "GS4"}:
                gs_paper = SUBJECT_TO_GS.get(subject_name.lower(), "GS3")

            return title, description, gs_paper

        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning(
                "generate_proposals_json_parse_failed",
                topic=topic_name,
                error=str(exc),
                raw=raw[:200],
            )
            # Graceful fallback
            fallback_gs = SUBJECT_TO_GS.get(subject_name.lower(), "GS3")
            return (
                f"Daily CA: {topic_name}",
                f"News update on {topic_name}. Review required.",
                fallback_gs,
            )
