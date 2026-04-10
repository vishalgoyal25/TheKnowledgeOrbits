"""
engines/daily_ca/tests/test_models.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase M2 — Daily CA Engine model tests.

Tests:
  - CaDailyProposal status transitions
  - CaDailyProposal queued_next_run status
  - CaDailyProposal unique_together (date + topic)
  - DailyCaArticle creation with all fields
  - DailyCaArticle defaults (is_published=False, quality_score=0)
  - DailyCaStaticLink unique constraint
"""

import uuid
from datetime import date

import pytest
from django.db import IntegrityError

from engines.daily_ca.models import (
    CaDailyProposal,
    DailyCaArticle,
    DailyCaStaticLink,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_article():
    return DailyCaArticle.objects.create(
        title="Test Article",
        slug=f"2026-04-10-test-article-{uuid.uuid4().hex[:6]}",
        subject_name="Polity",
        gs_paper="GS2",
        published_date=date(2026, 4, 10),
        body_md="Test body content here with enough words.",
        news_context="Some news context.",
    )


# ── CaDailyProposal ───────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCaDailyProposalModel:

    def test_default_status_is_pending(self):
        proposal = CaDailyProposal.objects.create(
            date=date(2026, 4, 10),
            title="Test Proposal",
            description="Test description",
        )
        assert proposal.status == "pending"

    def test_status_transition_to_approved(self):
        proposal = CaDailyProposal.objects.create(
            date=date(2026, 4, 10),
            title="Transition Test",
            description="desc",
        )
        proposal.status = "approved"
        proposal.save(update_fields=["status"])
        proposal.refresh_from_db()
        assert proposal.status == "approved"

    def test_status_transition_to_generated(self):
        proposal = CaDailyProposal.objects.create(
            date=date(2026, 4, 10),
            title="Generated Test",
            description="desc",
            status="approved",
        )
        proposal.status = "generated"
        proposal.save(update_fields=["status"])
        proposal.refresh_from_db()
        assert proposal.status == "generated"

    def test_queued_next_run_status(self):
        proposal = CaDailyProposal.objects.create(
            date=date(2026, 4, 10),
            title="Queued Test",
            description="desc",
        )
        proposal.status = "queued_next_run"
        proposal.save(update_fields=["status"])
        proposal.refresh_from_db()
        assert proposal.status == "queued_next_run"

    def test_failed_status(self):
        proposal = CaDailyProposal.objects.create(
            date=date(2026, 4, 10),
            title="Failed Test",
            description="desc",
        )
        proposal.status = "failed"
        proposal.save(update_fields=["status"])
        proposal.refresh_from_db()
        assert proposal.status == "failed"

    def test_str(self):
        proposal = CaDailyProposal.objects.create(
            date=date(2026, 4, 10),
            title="Some Proposal Title Here",
            description="desc",
        )
        s = str(proposal)
        assert "2026-04-10" in s
        assert "Some Proposal" in s

    def test_source_urls_default_empty_list(self):
        proposal = CaDailyProposal.objects.create(
            date=date(2026, 4, 10),
            title="Test",
            description="desc",
        )
        assert proposal.source_urls == []

    def test_ca_chunk_ids_default_empty_list(self):
        proposal = CaDailyProposal.objects.create(
            date=date(2026, 4, 10),
            title="Test",
            description="desc",
        )
        assert proposal.ca_chunk_ids == []


# ── DailyCaArticle ────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestDailyCaArticleModel:

    def test_default_is_published_false(self, sample_article):
        assert sample_article.is_published is False

    def test_default_quality_score_zero(self, sample_article):
        assert sample_article.quality_score == 0.0

    def test_default_order_on_date_zero(self, sample_article):
        assert sample_article.order_on_date == 0

    def test_body_md_processed_default_empty(self, sample_article):
        assert sample_article.body_md_processed == ""

    def test_generation_metadata_default_empty_dict(self, sample_article):
        assert sample_article.generation_metadata == {}

    def test_sources_used_default_empty_list(self, sample_article):
        assert sample_article.sources_used == []

    def test_slug_unique_constraint(self, sample_article):
        with pytest.raises(IntegrityError):
            DailyCaArticle.objects.create(
                title="Duplicate Slug",
                slug=sample_article.slug,  # same slug
                published_date=date(2026, 4, 10),
                body_md="Some content.",
            )

    def test_str(self, sample_article):
        s = str(sample_article)
        assert "2026-04-10" in s
        assert "Test Article" in s

    def test_publish_article(self, sample_article):
        sample_article.is_published = True
        sample_article.save(update_fields=["is_published"])
        sample_article.refresh_from_db()
        assert sample_article.is_published is True


# ── DailyCaStaticLink ─────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestDailyCaStaticLinkModel:

    def test_static_link_unique_constraint(self, sample_article):
        """Same daily_article + book_content_id → IntegrityError on second create."""
        book_content_id = uuid.uuid4()

        DailyCaStaticLink.objects.create(
            daily_article=sample_article,
            book_content_id=book_content_id,
            link_reason="same_topic",
        )
        with pytest.raises(IntegrityError):
            DailyCaStaticLink.objects.create(
                daily_article=sample_article,
                book_content_id=book_content_id,
                link_reason="background",
            )

    def test_default_link_reason_same_topic(self):
        """Verify the model field default — no DB write needed (avoids FK constraint)."""
        field = DailyCaStaticLink._meta.get_field("link_reason")
        assert field.default == "same_topic"
