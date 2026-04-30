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
  4. Top 30 topic groups max — sorted by combined relevance, diversity-capped
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
from engines.daily_ca.models import CaDailyProposal, DailyCaArticle

logger = structlog.get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_TOPICS_PER_RUN = 30  # Hard cap on proposals generated per run
MAX_GROQ_CALLS = 30  # Session safety cap
TOP_CHUNKS_PER_TOPIC = 3  # How many source chunks to collect per proposal
RELEVANCE_THRESHOLD = 5.0  # Minimum score from RelevanceScorerService

# Phase D — Subject diversity caps
# Ensures all 4 GS papers are represented in the daily proposal set.
# Without these caps, GS2 (Polity/IR) dominates because UPSC keywords are
# heavily weighted toward political news and India has high Polity news volume.
MAX_PER_GS_PAPER = 3  # No single GS paper can exceed 3 proposals (3×4 = 12 max)
MAX_PER_SUBJECT = 2  # No single subject can exceed 2 proposals within a GS paper

# ── GS Paper mapping — AUTHORITATIVE, deterministic, never overridden by LLM ─
# Keys: exact Subject.name values as seeded by seed_syllabus.py, plus lowercase
# fallback variants for robustness. GS assignment follows official UPSC syllabus.
SUBJECT_TO_GS: dict[str, str] = {
    # ══════════════════════════════════════════════════════════════════════════
    # GS 1 — History, Geography, Culture, Society
    # DB subjects: Indian Heritage & Culture | Modern Indian History |
    #              World History | Indian Society | Indian & World Geography
    # ══════════════════════════════════════════════════════════════════════════
    # Exact DB names (title-case)
    "Indian Heritage & Culture": "GS1",
    "Modern Indian History": "GS1",
    "World History": "GS1",
    "Indian Society": "GS1",
    "Indian & World Geography": "GS1",
    # Lowercase exact
    "indian heritage & culture": "GS1",
    "indian heritage and culture": "GS1",
    "modern indian history": "GS1",
    "world history": "GS1",
    "indian society": "GS1",
    "indian & world geography": "GS1",
    "indian and world geography": "GS1",
    # Common LLM hallucination variants
    "history": "GS1",
    "ancient history": "GS1",
    "medieval history": "GS1",
    "post-independence history": "GS1",
    "freedom struggle": "GS1",
    "colonial history": "GS1",
    "art and culture": "GS1",
    "art & culture": "GS1",
    "culture": "GS1",
    "heritage": "GS1",
    "society": "GS1",
    "social issues": "GS1",
    "social development": "GS1",
    "demography": "GS1",
    "population": "GS1",
    "urbanisation": "GS1",
    "women and society": "GS1",
    "geography": "GS1",
    "indian geography": "GS1",
    "physical geography": "GS1",
    "world geography": "GS1",
    "geomorphology": "GS1",
    "climatology": "GS1",
    "oceanography": "GS1",
    # ══════════════════════════════════════════════════════════════════════════
    # GS 2 — Polity, Governance, IR
    # DB subjects: Indian Polity & Constitution | Governance & Social Justice |
    #              International Relations
    # ══════════════════════════════════════════════════════════════════════════
    # Exact DB names (title-case)
    "Indian Polity & Constitution": "GS2",
    "Governance & Social Justice": "GS2",
    "International Relations": "GS2",
    # Lowercase exact
    "indian polity & constitution": "GS2",
    "indian polity and constitution": "GS2",
    "governance & social justice": "GS2",
    "governance and social justice": "GS2",
    "international relations": "GS2",
    # Common LLM hallucination variants — Polity
    "indian constitution & polity": "GS2",
    "indian constitution and polity": "GS2",
    "constitution of india": "GS2",
    "indian constitution": "GS2",
    "polity": "GS2",
    "indian polity": "GS2",
    "constitution": "GS2",
    "constitutional law": "GS2",
    "judiciary": "GS2",
    "parliament": "GS2",
    "executive": "GS2",
    "legislature": "GS2",
    "federalism": "GS2",
    "fundamental rights": "GS2",
    "law": "GS2",
    "rights": "GS2",
    "election": "GS2",
    "electoral reforms": "GS2",
    # Common LLM hallucination variants — Governance
    "governance": "GS2",
    "social justice": "GS2",
    "public administration": "GS2",
    "e-governance": "GS2",
    "welfare schemes": "GS2",
    "government schemes": "GS2",
    "health policy": "GS2",
    "education policy": "GS2",
    # Common LLM hallucination variants — IR
    "foreign affairs": "GS2",
    "foreign policy": "GS2",
    "india's foreign policy": "GS2",
    "diplomacy": "GS2",
    "bilateral relations": "GS2",
    "geopolitics": "GS2",
    "international affairs": "GS2",
    "global affairs": "GS2",
    "united nations": "GS2",
    "multilateral organisations": "GS2",
    # ══════════════════════════════════════════════════════════════════════════
    # GS 3 — Economy, S&T, Environment, Security, Disaster
    # DB subjects: Indian Economy | Science & Technology | Environment & Ecology |
    #              Internal Security | Disaster Management
    # ══════════════════════════════════════════════════════════════════════════
    # Exact DB names (title-case)
    "Indian Economy": "GS3",
    "Science & Technology": "GS3",
    "Environment & Ecology": "GS3",
    "Internal Security": "GS3",
    "Disaster Management": "GS3",
    # Lowercase exact
    "indian economy": "GS3",
    "science & technology": "GS3",
    "science and technology": "GS3",
    "environment & ecology": "GS3",
    "environment and ecology": "GS3",
    "internal security": "GS3",
    "disaster management": "GS3",
    # Common LLM hallucination variants — Economy
    "economy": "GS3",
    "economics": "GS3",
    "economic development": "GS3",
    "economic affairs": "GS3",
    "macroeconomics": "GS3",
    "fiscal policy": "GS3",
    "monetary policy": "GS3",
    "banking": "GS3",
    "infrastructure": "GS3",
    "agriculture": "GS3",
    "agriculture and rural development": "GS3",
    "agriculture & rural development": "GS3",
    "food security": "GS3",
    "industry": "GS3",
    "trade": "GS3",
    "investment": "GS3",
    "budget": "GS3",
    # Common LLM hallucination variants — Science & Tech
    "technology": "GS3",
    "science": "GS3",
    "space": "GS3",
    "space technology": "GS3",
    "nuclear": "GS3",
    "nuclear technology": "GS3",
    "biotechnology": "GS3",
    "artificial intelligence": "GS3",
    "defence technology": "GS3",
    "it and technology": "GS3",
    # Common LLM hallucination variants — Environment
    "environment": "GS3",
    "ecology": "GS3",
    "climate": "GS3",
    "climate change": "GS3",
    "biodiversity": "GS3",
    "conservation": "GS3",
    "pollution": "GS3",
    "renewable energy": "GS3",
    "sustainable development": "GS3",
    # Common LLM hallucination variants — Security
    "security": "GS3",
    "defence": "GS3",
    "terrorism": "GS3",
    "insurgency": "GS3",
    "border security": "GS3",
    "cybersecurity": "GS3",
    # Common LLM hallucination variants — Disaster
    "disaster": "GS3",
    "natural disaster": "GS3",
    "disaster risk reduction": "GS3",
    # ══════════════════════════════════════════════════════════════════════════
    # GS 4 — Ethics
    # DB subject: Ethics, Integrity & Aptitude
    # ══════════════════════════════════════════════════════════════════════════
    # Exact DB name (title-case)
    "Ethics, Integrity & Aptitude": "GS4",
    # Lowercase exact
    "ethics, integrity & aptitude": "GS4",
    "ethics, integrity and aptitude": "GS4",
    # Common LLM hallucination variants
    "ethics": "GS4",
    "integrity": "GS4",
    "aptitude": "GS4",
    "moral philosophy": "GS4",
    "values": "GS4",
    "public administration ethics": "GS4",
    "emotional intelligence": "GS4",
    "attitude": "GS4",
}

# ── GROQ Prompt ───────────────────────────────────────────────────────────────
# GS paper is NOT asked from LLM — derived deterministically from subject_name
# via SUBJECT_TO_GS after the GROQ call. LLM only writes the human-readable parts.
_PROPOSAL_PROMPT = """You are a senior editor at a public affairs knowledge platform.
Your readers are curious citizens, researchers, policymakers, and informed professionals.

Based on the news excerpts below about "{topic_name}", write a concise article proposal.

News excerpts:
{news_text}

Return ONLY valid JSON (no markdown fences, no extra text):
{{
  "title": "A sharp, specific, newsworthy article title — 10 to 15 words. Must reflect today's specific development, not a generic topic label.",
  "description": "Exactly 3 sentences. Sentence 1: What happened today and the specific trigger. Sentence 2: The broader context or significance of this development. Sentence 3: One concrete fact, figure, or implication that makes this worth reading."
}}

Rules:
- Title must name the specific event/decision/development — not just the topic
- Description must be factual and specific — no vague language
- Do NOT mention UPSC, GS paper, exam, aspirants, or syllabus anywhere
- Do NOT use filler phrases like "In recent times", "It is pertinent to note", "This is important"
- Return only the JSON object — no markdown, no explanation"""


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

        # Step 3b: Deduplicate by chunk overlap — remove proposals that share
        # source chunks with a higher-scoring proposal.
        # Threshold lowered 0.6 → 0.4 (Phase D fix): with only 3 chunks per group,
        # sharing 2 chunks yields Jaccard = 0.50 which slipped past the old 0.60 guard.
        # Two topics covering the same news story routinely share 1–2 chunks and now
        # get correctly collapsed into the higher-scoring proposal.
        pre_dedup_count = len(topic_groups)
        topic_groups = self._deduplicate_by_chunk_overlap(topic_groups, threshold=0.4)
        removed = pre_dedup_count - len(topic_groups)
        if removed:
            self.stdout.write(
                f"  → {removed} topic group(s) removed by chunk deduplication "
                f"(Jaccard > 0.6), {len(topic_groups)} remain"
            )

        # Step 4: Sort by combined relevance score, cap at MAX_TOPICS_PER_RUN
        sorted_groups = sorted(
            topic_groups.items(),
            key=lambda x: x[1]["combined_score"],
            reverse=True,
        )[:MAX_TOPICS_PER_RUN]

        # Step 4b: Apply subject diversity cap — prevent any GS paper or subject
        # from dominating. Walk highest-scored first; admit greedily until cap hit.
        pre_cap_count = len(sorted_groups)
        sorted_groups = self._apply_diversity_cap(sorted_groups)

        self.stdout.write(
            f"  → Processing top {len(sorted_groups)} topic groups "
            f"after diversity cap (was {pre_cap_count}, "
            f"cap: GS paper ≤{MAX_PER_GS_PAPER}, subject ≤{MAX_PER_SUBJECT})"
        )

        # Step 5: Generate proposals
        created = 0
        skipped = 0
        failed = 0
        groq_calls = 0

        # Phase I — Layer 2: fetch recent published titles ONCE before the loop.
        # Single DB query, titles only (values_list flat=True).
        # 3-day window: a news topic continuous for > 3 days warrants a new article.
        # 3 days × max 10 articles/day = max 30 strings — negligible memory/time.
        recent_published_titles: list[str] = list(
            DailyCaArticle.objects.using(db_alias)
            .filter(
                published_date__gte=target_date - timedelta(days=3),
                is_published=True,
            )
            .values_list("title", flat=True)
        )
        if recent_published_titles:
            self.stdout.write(
                f"  → {len(recent_published_titles)} published article(s) in last 3 days "
                f"loaded for duplicate check"
            )

        # Phase I — Layer 1: track titles generated in THIS run (intra-day dedup).
        # Mutated in-place by _process_topic_group() on each successful save.
        generated_titles: list[str] = []

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
                    generated_titles=generated_titles,
                    recent_published_titles=recent_published_titles,
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
                elif result == "skipped_title_overlap":
                    skipped += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"  ~ [dedup] {topic_obj.name[:60]} (title too similar to recent article)"
                        )
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

    @staticmethod
    def _title_token_overlap(title_a: str, title_b: str) -> float:
        """
        Phase I — Jaccard token overlap between two proposal/article titles.

        Strips common stopwords and punctuation, then computes:
            overlap = |tokens_a ∩ tokens_b| / |tokens_a ∪ tokens_b|

        Returns 0.0–1.0. No external libraries — pure set operations.
        Used for both Layer 1 (intra-day) and Layer 2 (3-day lookback).
        """
        _STOPWORDS = {
            "the",
            "a",
            "an",
            "of",
            "in",
            "to",
            "and",
            "for",
            "on",
            "at",
            "is",
            "are",
            "was",
            "were",
            "india",
            "its",
            "by",
            "with",
            "as",
            "from",
            "that",
            "this",
            "be",
            "has",
            "have",
            "it",
            "will",
            "about",
            "how",
            "why",
            "what",
            "who",
            "when",
            "where",
            "which",
            "new",
            "now",
            "over",
            "after",
            "amid",
            # Fallback-title noise: "X — Latest Development" tokens should not
            # inflate Jaccard similarity between otherwise unrelated proposals.
            "latest",
            "development",
            "recent",
            "update",
        }

        def _tokens(title: str) -> set[str]:
            return {
                w.lower().strip(".,:-—\"'()")
                for w in title.split()
                if w.lower().strip(".,:-—\"'()") not in _STOPWORDS and len(w) > 1
            }

        tokens_a = _tokens(title_a)
        tokens_b = _tokens(title_b)
        if not tokens_a or not tokens_b:
            return 0.0
        return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)

    @staticmethod
    def _deduplicate_by_chunk_overlap(
        topic_groups: dict,
        threshold: float = 0.6,
    ) -> dict:
        """
        Phase E — Cross-Proposal Chunk Deduplication.

        A CAChunk with multiple CATopicLink entries gets added to several topic
        groups. Two proposals can end up with heavily overlapping ca_chunk_ids,
        causing the LLM to receive the same source material and generate two
        articles on the same story.

        Strategy: greedy Jaccard deduplication.
          1. Sort topics by combined_score descending (highest quality first).
          2. Walk each topic; compute Jaccard similarity of its chunk ID set
             against every already-admitted topic.
          3. If any admitted topic shares > threshold fraction of chunks,
             skip (remove) this topic — the higher-scoring duplicate was kept.
          4. Return dict of admitted topics only.

        Jaccard(A, B) = |A ∩ B| / |A ∪ B|

        threshold=0.6 means: if 60%+ of source chunks are shared, it's the same
        story. Adjust down to 0.5 for stricter deduplication.
        """
        if not topic_groups:
            return topic_groups

        # Sort highest-score first so the better proposal is always kept
        sorted_items = sorted(
            topic_groups.items(),
            key=lambda x: x[1]["combined_score"],
            reverse=True,
        )

        admitted: list[tuple] = []
        admitted_chunk_sets: list[set[str]] = []

        for topic_obj, group_data in sorted_items:
            chunk_ids: set[str] = {str(c.id) for c in group_data["chunks"]}

            is_duplicate = False
            for existing_set in admitted_chunk_sets:
                intersection = len(chunk_ids & existing_set)
                union = len(chunk_ids | existing_set)
                if union == 0:
                    continue
                jaccard = intersection / union
                if jaccard > threshold:
                    is_duplicate = True
                    logger.info(
                        "generate_proposals_chunk_dedup_removed",
                        topic=topic_obj.name,
                        jaccard=round(jaccard, 3),
                        threshold=threshold,
                    )
                    break

            if not is_duplicate:
                admitted.append((topic_obj, group_data))
                admitted_chunk_sets.append(chunk_ids)

        return dict(admitted)

    @staticmethod
    def _apply_diversity_cap(
        sorted_groups: list[tuple],
    ) -> list[tuple]:
        """
        Phase D — Subject Diversity Cap.

        Walks topics highest-score-first and admits each topic only if
        both caps are still open:
          • gs_paper_counts[gs_paper] < MAX_PER_GS_PAPER
          • subject_counts[subject_name] < MAX_PER_SUBJECT

        Topics that exceed a cap are not dropped entirely — they are placed
        in an overflow list and appended AFTER all primary slots are filled,
        so rare GS papers that genuinely have no other news still get
        representation up to the global MAX_TOPICS_PER_RUN limit.

        This means:
          - Under normal news days: balanced 3 GS1 / 3 GS2 / 3 GS3 / 3 GS4
          - If one GS paper has zero news: other papers fill the slack
          - High-score topics from a capped paper are never silently discarded;
            they appear at the end as lower-priority overflow

        Returns a new sorted list — does NOT mutate the input.
        """
        from collections import defaultdict

        gs_paper_counts: dict[str, int] = defaultdict(int)
        subject_counts: dict[str, int] = defaultdict(int)

        primary: list[tuple] = []
        overflow: list[tuple] = []

        for topic_obj, group_data in sorted_groups:
            subject_name = Command._get_subject_name(topic_obj)
            gs_paper = Command._derive_gs_paper(subject_name)

            gs_ok = gs_paper_counts[gs_paper] < MAX_PER_GS_PAPER
            subj_ok = subject_counts[subject_name] < MAX_PER_SUBJECT

            if gs_ok and subj_ok:
                primary.append((topic_obj, group_data))
                gs_paper_counts[gs_paper] += 1
                subject_counts[subject_name] += 1
            else:
                overflow.append((topic_obj, group_data))

        result = primary + overflow
        logger.info(
            "generate_proposals_diversity_cap_applied",
            primary_slots=len(primary),
            overflow_slots=len(overflow),
            gs_paper_distribution=dict(gs_paper_counts),
        )
        return result

    def _process_topic_group(
        self,
        topic,
        group_data: dict,
        target_date: date,
        dry_run: bool,
        db_alias: str,
        generated_titles: list[str] | None = None,
        recent_published_titles: list[str] | None = None,
    ) -> str:
        """
        For one topic group:
          - Check if proposal already exists (idempotent)
          - Derive subject_name from topic → module → subject (DB)
          - Derive gs_paper deterministically from subject_name (never from LLM)
          - Call GROQ for title + description only
          - Phase I Layer 2: check title against last 3 days published articles
          - Phase I Layer 1: check title against other proposals in THIS run
          - Save CaDailyProposal

        Returns: "created" | "skipped" | "skipped_title_overlap" | "dry_run"

        generated_titles: mutable list — appended to on successful save so each
                          subsequent call in the same loop sees already-saved titles.
        recent_published_titles: read-only, pre-fetched once before the loop.
        """
        if generated_titles is None:
            generated_titles = []
        if recent_published_titles is None:
            recent_published_titles = []

        # Phase D fix: split overlap thresholds by dedup layer.
        # Intra-day (Layer 1): 0.45 — raised from 0.35 to reduce false positives.
        #   0.35 was too aggressive: fallback titles ("X — Latest Development") share
        #   "latest" / "development" tokens and were pushing unrelated topics over the
        #   threshold. 0.45 still catches genuine same-story duplicates.
        # 3-day lookback (Layer 2): 0.5 — cross-day comparison is less sensitive;
        #   a legitimate follow-up article shares many words with its predecessor.
        _INTRADAY_OVERLAP_THRESHOLD = 0.45
        _RECENT_OVERLAP_THRESHOLD = 0.5

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
        subject_name = self._canonicalize_subject_name(
            subject_name, topic.name, db_alias
        )

        # GROQ call — title + description only
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

        # ── Phase I Layer 2: 3-day lookback against published articles ──────────
        # recent_published_titles fetched once before loop — pure set ops, zero I/O
        for recent_title in recent_published_titles:
            overlap = self._title_token_overlap(title, recent_title)
            if overlap >= _RECENT_OVERLAP_THRESHOLD:
                logger.info(
                    "generate_proposals_skipped_recent_duplicate",
                    topic=topic.name,
                    proposal_title=title,
                    matched_published_title=recent_title,
                    overlap=round(overlap, 3),
                    lookback_days=3,
                )
                return "skipped_title_overlap"

        # ── Phase I Layer 1: intra-day dedup against this run's saved titles ────
        # Phase D: save with status='duplicate' (not silently discarded) so the
        # record is visible in admin/logs and the idempotency check on re-runs
        # correctly skips it without re-generating a new proposal for the same topic.
        # Uses the lower 0.35 threshold — same-day proposals about the same news
        # story often share only 35–45% content tokens across GROQ-generated titles.
        for existing_title in generated_titles:
            overlap = self._title_token_overlap(title, existing_title)
            if overlap >= _INTRADAY_OVERLAP_THRESHOLD:
                logger.warning(
                    "generate_proposals_intraday_duplicate_saved",
                    topic=topic.name,
                    proposal_title=title,
                    matched_title=existing_title,
                    overlap=round(overlap, 3),
                )
                if not dry_run:
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
                            status="duplicate",
                        )
                return "skipped_title_overlap"

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

        # Track for Layer 1 intra-day dedup on subsequent iterations
        generated_titles.append(title)

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
    def _canonicalize_subject_name(
        subject_name: str, topic_name: str, db_alias: str
    ) -> str:
        """
        Phase A3 — Fuzzy-match fallback for subject_name.

        Called after _get_subject_name(). If subject_name is already non-empty
        (FK chain resolved successfully), returns it unchanged immediately.

        When subject_name == "" (broken FK chain — topic has no module/subject),
        fuzzy-matches topic_name against all Subject.name values in the DB using
        difflib.get_close_matches (threshold 0.75).

        Returns the best-matching Subject.name (canonical DB spelling) so that
        _derive_gs_paper() gets the best possible input rather than blindly
        defaulting to GS3.

        Failure modes:
          - No subjects in DB → returns ""
          - No close match (threshold 0.75) → returns ""
          - Any exception → logs warning, returns "" (never raises)
        """
        # Fast path: FK chain already resolved — nothing to do
        if subject_name:
            return subject_name

        if not topic_name or not topic_name.strip():
            return ""

        try:
            from difflib import get_close_matches

            from engines.knowledge.models import Subject

            subject_names: list[str] = list(
                Subject.objects.using(db_alias).values_list("name", flat=True)
            )
            if not subject_names:
                return ""

            # Build lowercase → canonical mapping for case-insensitive matching
            lower_map: dict[str, str] = {s.lower(): s for s in subject_names}
            topic_lower = topic_name.lower().strip()

            matches = get_close_matches(
                topic_lower, list(lower_map.keys()), n=1, cutoff=0.75
            )

            if matches:
                canonical = lower_map[matches[0]]
                logger.info(
                    "generate_proposals_subject_fuzzy_matched",
                    topic_name=topic_name,
                    matched_subject=canonical,
                    similarity_threshold=0.75,
                )
                return canonical

            logger.info(
                "generate_proposals_subject_fuzzy_no_match",
                topic_name=topic_name,
                candidates_checked=len(subject_names),
            )
            return ""

        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.warning(
                "generate_proposals_subject_canonicalize_failed",
                topic_name=topic_name,
                error=str(exc)[:200],
            )
            return ""

    @staticmethod
    def _derive_gs_paper(subject_name: str) -> str:
        """
        Derives GS paper deterministically from subject_name.
        Checks exact name first, then lowercase, then partial word match.
        Never falls back to LLM — always returns a valid GS1/GS2/GS3/GS4 string.
        Default: GS3 (broadest subject — safe fallback).
        """
        if not subject_name:
            return "GS3"

        # Pass 1: exact match (handles canonical DB names like "Indian Polity & Constitution")
        if subject_name in SUBJECT_TO_GS:
            return SUBJECT_TO_GS[subject_name]

        # Pass 2: lowercase match (handles LLM free-text variants)
        lower = subject_name.lower().strip()
        if lower in SUBJECT_TO_GS:
            return SUBJECT_TO_GS[lower]

        # Pass 3: check if any dict key is contained within the subject_name
        # (handles cases like "Indian Economy and Agriculture" → matches "indian economy")
        for key, gs in SUBJECT_TO_GS.items():
            if key in lower or lower in key:
                return gs

        logger.warning(
            "generate_proposals_gs_fallback",
            subject_name=subject_name,
            fallback="GS3",
        )
        return "GS3"

    @staticmethod
    def _parse_groq_response(
        raw: str, topic_name: str, subject_name: str
    ) -> tuple[str, str, str]:
        """
        Parse GROQ JSON response → (title, description, gs_paper).

        gs_paper is NEVER taken from the LLM response — it is derived
        deterministically from subject_name via _derive_gs_paper().
        LLM is only trusted for: title, description.

        Falls back gracefully if JSON is malformed.
        """
        # gs_paper: always derived from subject, never from LLM
        gs_paper = Command._derive_gs_paper(subject_name)

        try:
            # Strip markdown fences
            cleaned = re.sub(r"```(?:json)?", "", raw).strip()

            # Pre-sanitise common LLM JSON defects before any parse attempt:
            #   • Trailing commas — e.g. {"title": "...", "description": "...",}
            #     These are valid JS but illegal JSON and cause json.loads to raise
            #     "Illegal trailing comma" or "Expecting property name".
            cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)

            # Phase D — Stricter JSON extraction (3 attempts, most-specific first):
            #   Attempt 1: direct parse — LLM returned clean JSON with no preamble
            #   Attempt 2: find an object that contains both required keys
            #   Attempt 3: fall back to the first {...} block (old behaviour)
            data = None
            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                pass

            if data is None:
                # Attempt 2: object containing "title" and "description" keys
                match = re.search(
                    r'\{[^{}]*"title"[^{}]*"description"[^{}]*\}',
                    cleaned,
                    re.DOTALL,
                )
                if match:
                    try:
                        data = json.loads(match.group())
                    except json.JSONDecodeError:
                        pass

            if data is None:
                # Attempt 3: any {...} block — greedy, same as original behaviour
                match = re.search(r"\{.*\}", cleaned, re.DOTALL)
                if not match:
                    raise ValueError("No JSON object found in GROQ response")
                data = json.loads(match.group())

            title = str(data.get("title", "")).strip()
            description = str(data.get("description", "")).strip()

            # Validate title — log WARNING (visible in Render logs) when fallback fires
            if not title or len(title) < 5:
                logger.warning(
                    "generate_proposals_fallback_title_used",
                    topic=topic_name,
                    reason="title_missing_or_too_short",
                    raw_title=title[:80],
                )
                title = f"{topic_name} — Latest Development"

            # Validate description
            if not description or len(description) < 20:
                description = (
                    f"Recent news on {topic_name}. Review source articles for details."
                )

            # Strip any UPSC exam language that may have leaked through despite prompt
            _exam_phrases = (
                "upsc",
                "gs paper",
                "mains",
                "prelims",
                "aspirants",
                "civil services",
                "exam perspective",
                "important for",
            )
            for phrase in _exam_phrases:
                if phrase in title.lower():
                    logger.warning(
                        "generate_proposals_fallback_title_used",
                        topic=topic_name,
                        reason="exam_phrase_in_title",
                        phrase_matched=phrase,
                        raw_title=title[:80],
                    )
                    title = f"{topic_name} — Latest Development"
                if phrase in description.lower():
                    description = description.replace(phrase, "").strip().strip(".,;")

            return title, description, gs_paper

        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning(
                "generate_proposals_json_parse_failed",
                topic=topic_name,
                error=str(exc),
                raw=raw[:200],
            )
            logger.warning(
                "generate_proposals_fallback_title_used",
                topic=topic_name,
                reason="json_parse_failed",
                error=str(exc)[:100],
            )
            return (
                f"{topic_name} — Latest Development",
                f"Recent development on {topic_name}. Review source articles.",
                gs_paper,  # still derived from subject, even on JSON failure
            )
