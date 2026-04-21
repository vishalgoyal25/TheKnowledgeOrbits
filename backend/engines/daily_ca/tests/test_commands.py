"""
engines/daily_ca/tests/test_commands.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Unit tests for generate_ca_proposals management command utility helpers.

ALL tests are pure unit tests — no DB access, no HTTP, no GROQ calls.
Only the static/pure utility methods of the Command class are tested here:
  - _title_token_overlap()
  - _apply_diversity_cap()
  - _derive_gs_paper()
  - _parse_date()
"""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import MagicMock, patch
import pytest
from io import StringIO
import uuid


# ─────────────────────────────────────────────────────────────────────────────
# Helper: build a minimal fake topic object for _apply_diversity_cap tests
# ─────────────────────────────────────────────────────────────────────────────


def _make_topic(subject_name: str, topic_name: str = "Test Topic") -> MagicMock:
    """
    Build a MagicMock that mimics a Topic ORM object.
    topic.module.subject.name → subject_name
    topic.name → topic_name
    """
    topic = MagicMock()
    topic.name = topic_name
    topic.module.subject.name = subject_name
    return topic


# ─────────────────────────────────────────────────────────────────────────────
# _title_token_overlap
# ─────────────────────────────────────────────────────────────────────────────


class TestTitleTokenOverlap(unittest.TestCase):
    """Tests for Command._title_token_overlap() — pure string Jaccard logic."""

    def _overlap(self, a: str, b: str) -> float:
        from engines.daily_ca.management.commands.generate_ca_proposals import Command

        return Command._title_token_overlap(a, b)

    def test_identical_titles_return_one(self) -> None:
        """Identical non-trivial titles must return 1.0."""
        score = self._overlap(
            "Supreme Court Upholds Electoral Bond Scheme",
            "Supreme Court Upholds Electoral Bond Scheme",
        )
        assert score == 1.0

    def test_completely_different_titles_return_zero(self) -> None:
        """Completely different titles have 0.0 overlap."""
        score = self._overlap(
            "Railway Budget Allocation 2025", "Cyclone Warning Kerala Coast"
        )
        assert score == 0.0

    def test_partial_overlap_returns_fractional_score(self) -> None:
        """Titles with some shared words return a value strictly between 0 and 1."""
        score = self._overlap(
            "Supreme Court Issues Order on Electoral Bonds",
            "Supreme Court Rules Against Electoral Scheme",
        )
        assert 0.0 < score < 1.0

    def test_stopwords_are_excluded_from_comparison(self) -> None:
        """
        Titles that differ only by stopwords ('the', 'a', 'in', etc.)
        should have a high overlap — stopwords must not inflate the union set.
        """
        score = self._overlap(
            "Reform of the Election Commission",
            "Reform of Election Commission",
        )
        # After stripping stopwords both reduce to roughly the same tokens
        assert score > 0.7

    def test_empty_title_a_returns_zero(self) -> None:
        """Empty first title must return 0.0 without raising."""
        score = self._overlap("", "Budget Session Parliament 2025")
        assert score == 0.0

    def test_empty_title_b_returns_zero(self) -> None:
        """Empty second title must return 0.0 without raising."""
        score = self._overlap("Budget Session Parliament 2025", "")
        assert score == 0.0

    def test_both_empty_returns_zero(self) -> None:
        """Both empty titles must return 0.0 without raising."""
        score = self._overlap("", "")
        assert score == 0.0

    def test_return_type_is_float(self) -> None:
        """Return value must always be a float."""
        score = self._overlap(
            "Parliament Session Budget", "Climate Change India Policy"
        )
        assert isinstance(score, float)


# ─────────────────────────────────────────────────────────────────────────────
# _derive_gs_paper
# ─────────────────────────────────────────────────────────────────────────────


class TestDeriveGsPaper(unittest.TestCase):
    """Tests for Command._derive_gs_paper() — deterministic GS paper derivation."""

    def _derive(self, subject: str) -> str:
        from engines.daily_ca.management.commands.generate_ca_proposals import Command

        return Command._derive_gs_paper(subject)

    def test_exact_db_name_gs2_polity(self) -> None:
        """Canonical DB name 'Indian Polity & Constitution' → GS2."""
        assert self._derive("Indian Polity & Constitution") == "GS2"

    def test_exact_db_name_gs1_history(self) -> None:
        """Canonical DB name 'Modern Indian History' → GS1."""
        assert self._derive("Modern Indian History") == "GS1"

    def test_exact_db_name_gs3_economy(self) -> None:
        """Canonical DB name 'Indian Economy' → GS3."""
        assert self._derive("Indian Economy") == "GS3"

    def test_exact_db_name_gs4_ethics(self) -> None:
        """Canonical DB name 'Ethics, Integrity & Aptitude' → GS4."""
        assert self._derive("Ethics, Integrity & Aptitude") == "GS4"

    def test_lowercase_variant_gs2(self) -> None:
        """Lowercase variant 'polity' resolves to GS2."""
        assert self._derive("polity") == "GS2"

    def test_lowercase_variant_gs3_environment(self) -> None:
        """Lowercase 'environment' resolves to GS3."""
        assert self._derive("environment") == "GS3"

    def test_partial_match_gs3(self) -> None:
        """'ecology and biodiversity' partially matches 'ecology' → GS3."""
        assert self._derive("ecology and biodiversity") == "GS3"

    def test_unknown_subject_defaults_to_gs3(self) -> None:
        """Completely unknown subject name falls back to GS3 (safe default)."""
        assert self._derive("Totally Unknown Subject XYZ") == "GS3"

    def test_empty_string_defaults_to_gs3(self) -> None:
        """Empty subject name falls back to GS3 without raising."""
        assert self._derive("") == "GS3"

    def test_return_type_is_string(self) -> None:
        """Return value is always a string starting with 'GS'."""
        result = self._derive("climate change")
        assert isinstance(result, str)
        assert result.startswith("GS")


# ─────────────────────────────────────────────────────────────────────────────
# _parse_date
# ─────────────────────────────────────────────────────────────────────────────


class TestParseDate(unittest.TestCase):
    """Tests for Command._parse_date() — date string parsing."""

    def _parse(self, date_str: str) -> date:
        from engines.daily_ca.management.commands.generate_ca_proposals import Command

        return Command._parse_date(date_str)

    def test_today_returns_date_object(self) -> None:
        """'today' returns today's date as a date object."""
        result = self._parse("today")
        assert isinstance(result, date)
        assert result == date.today()

    def test_today_case_insensitive(self) -> None:
        """'TODAY' (uppercase) is also accepted."""
        result = self._parse("TODAY")
        assert result == date.today()

    def test_valid_date_string_parsed_correctly(self) -> None:
        """'2026-04-10' is parsed to date(2026, 4, 10)."""
        result = self._parse("2026-04-10")
        assert result == date(2026, 4, 10)

    def test_valid_date_at_year_boundary(self) -> None:
        """'2025-01-01' is parsed to date(2025, 1, 1)."""
        result = self._parse("2025-01-01")
        assert result == date(2025, 1, 1)

    def test_invalid_format_raises_value_error(self) -> None:
        """Invalid format string raises ValueError with a descriptive message."""
        with self.assertRaises(ValueError) as ctx:
            self._parse("10-04-2026")  # DD-MM-YYYY — wrong format
        assert "Invalid date format" in str(ctx.exception)

    def test_garbage_string_raises_value_error(self) -> None:
        """Garbage input raises ValueError."""
        with self.assertRaises(ValueError):
            self._parse("not-a-date")


# ─────────────────────────────────────────────────────────────────────────────
# _apply_diversity_cap
# ─────────────────────────────────────────────────────────────────────────────


class TestApplyDiversityCap(unittest.TestCase):
    """
    Tests for Command._apply_diversity_cap().

    Uses mock topic objects — no DB required.
    """

    def _cap(self, groups: list[tuple]) -> list[tuple]:
        from engines.daily_ca.management.commands.generate_ca_proposals import Command

        return Command._apply_diversity_cap(groups)

    def _make_groups(self, subject_score_pairs: list[tuple[str, float]]) -> list[tuple]:
        """Build a sorted_groups list from (subject_name, score) pairs."""
        return [
            (
                _make_topic(subject, f"Topic {i}"),
                {"combined_score": score},
            )
            for i, (subject, score) in enumerate(subject_score_pairs)
        ]

    def test_empty_input_returns_empty(self) -> None:
        """Empty input list returns empty list."""
        assert self._cap([]) == []

    def test_all_different_subjects_admitted_up_to_cap(self) -> None:
        """
        Four topics from four different GS papers (one each) are all admitted
        in primary slots — no overflow.
        """
        groups = self._make_groups(
            [
                ("Indian Polity & Constitution", 9.0),  # GS2
                ("Modern Indian History", 8.0),  # GS1
                ("Indian Economy", 7.0),  # GS3
                ("Ethics, Integrity & Aptitude", 6.0),  # GS4
            ]
        )
        result = self._cap(groups)
        # All 4 should appear (4 different GS papers, 1 each — well under cap)
        assert len(result) == 4

    def test_same_gs_paper_capped_at_max_per_gs(self) -> None:
        """
        More than MAX_PER_GS_PAPER topics from the same GS paper: overflow
        entries must still be present (appended after primary), not dropped.
        MAX_PER_GS_PAPER = 3, so 5 GS2 topics → 3 primary + 2 overflow = 5 total.
        """
        groups = self._make_groups(
            [
                ("Indian Polity & Constitution", 10.0),
                ("Governance & Social Justice", 9.0),
                ("International Relations", 8.0),
                ("Indian Polity & Constitution", 7.0),  # 4th GS2 → overflow
                ("Indian Polity & Constitution", 6.0),  # 5th GS2 → overflow
            ]
        )
        result = self._cap(groups)
        # All 5 must appear — overflow is appended, never dropped
        assert len(result) == 5

    def test_output_is_a_list(self) -> None:
        """Return value is a list (not a dict, not None)."""
        groups = self._make_groups([("Indian Economy", 5.0)])
        result = self._cap(groups)
        assert isinstance(result, list)

    def test_higher_scored_topic_appears_before_overflow(self) -> None:
        """
        When a subject hits MAX_PER_SUBJECT, the lower-scored topics move to
        overflow and appear after the primary topics in the result list.
        The highest-scored GS2 topic must appear before a lower-scored overflow.
        """
        # 3 GS2 topics → all primary (hits MAX_PER_GS_PAPER=3)
        # 4th GS2 topic with lower score → overflow (appended last)
        groups = self._make_groups(
            [
                ("Indian Polity & Constitution", 10.0),  # primary
                ("Governance & Social Justice", 9.0),  # primary
                ("International Relations", 8.0),  # primary
                ("Indian Polity & Constitution", 2.0),  # overflow
            ]
        )
        result = self._cap(groups)
        assert len(result) == 4
        # The overflow topic (score=2.0) is the last topic object
        last_topic = result[-1][0]
        assert last_topic.module.subject.name == "Indian Polity & Constitution"


# ─────────────────────────────────────────────────────────────────────────────
# backfill_daily_ca_embeddings management command
# ─────────────────────────────────────────────────────────────────────────────


_EMB_BATCH = "engines.content.services.embedding_service.EmbeddingService.generate_embeddings_batch"
_EMB_SINGLE = (
    "engines.content.services.embedding_service.EmbeddingService.generate_embedding"
)


@pytest.mark.django_db
class TestBackfillDailyCaEmbeddingsCommand(unittest.TestCase):
    """
    Tests for the backfill_daily_ca_embeddings management command.

    DB access is used for article/embedding creation.
    EmbeddingService is mocked to avoid HF API calls.

    Both generate_embeddings_batch AND generate_embedding are patched
    together in every test — the post_save signal fires generate_embedding
    (which internally delegates to generate_embeddings_batch), so patching
    only one of them leaves the mock vulnerable to signal-thread interference.
    """

    def _call_command(self, *args, **kwargs):
        from django.core.management import call_command

        out = StringIO()
        call_command("backfill_daily_ca_embeddings", *args, stdout=out, **kwargs)
        return out.getvalue()

    def _make_article(
        self, title: str = "Backfill Article", published: bool = True
    ) -> object:
        from engines.daily_ca.models import DailyCaArticle

        return DailyCaArticle.objects.create(
            title=title,
            slug=f"2026-04-22-bf-{uuid.uuid4().hex[:6]}",
            published_date=date(2026, 4, 22),
            body_md="Some body content.",
            is_published=published,
        )

    def test_nothing_to_do_when_all_embedded(self):
        """When all published articles are already embedded, prints success and exits."""
        from engines.content.models import Embedding

        article = self._make_article()
        Embedding.objects.create(
            content_type="daily_ca_article",
            content_id=article.id,
            vector=[0.1] * 384,
            model_name="all-MiniLM-L6-v2",
        )

        with patch(_EMB_SINGLE, return_value=[0.1] * 384):
            with patch(_EMB_BATCH) as mock_batch:
                output = self._call_command()

        mock_batch.assert_not_called()
        assert "Nothing to do" in output or "already have embeddings" in output

    def test_dry_run_shows_ids_without_saving(self):
        """--dry-run prints what would be processed without creating embeddings."""
        from engines.content.models import Embedding

        article = self._make_article(title="Dry Run Article")

        with patch(_EMB_SINGLE, return_value=[0.5] * 384):
            with patch(_EMB_BATCH) as mock_batch:
                self._call_command("--dry-run")

        mock_batch.assert_not_called()
        assert not Embedding.objects.filter(
            content_type="daily_ca_article", content_id=article.id
        ).exists()

    def test_embeds_missing_articles(self):
        """Command creates Embedding records for published articles with none."""
        from engines.content.models import Embedding

        article = self._make_article(title="Should Be Embedded")

        with patch(_EMB_SINGLE, return_value=[0.4] * 384):
            with patch(_EMB_BATCH, return_value=[[0.4] * 384]):
                output = self._call_command()

        assert Embedding.objects.filter(
            content_type="daily_ca_article", content_id=article.id
        ).exists()
        assert "Backfill complete" in output

    def test_skips_unpublished_articles(self):
        """Unpublished drafts must never be embedded by the backfill command."""
        from engines.content.models import Embedding

        from engines.daily_ca.models import DailyCaArticle

        # Remove any published articles left by earlier tests in this class
        DailyCaArticle.objects.filter(is_published=True).delete()
        draft = self._make_article(title="Draft Should Be Skipped", published=False)

        with patch(_EMB_SINGLE, return_value=[]):
            with patch(_EMB_BATCH, return_value=[]) as mock_batch:
                self._call_command()

        mock_batch.assert_not_called()
        assert not Embedding.objects.filter(
            content_type="daily_ca_article", content_id=draft.id
        ).exists()
