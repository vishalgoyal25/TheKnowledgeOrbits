"""
engines/daily_ca/tests/test_views.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase M2 — Daily CA API view tests.

Uses Django test client (no external calls).

Tests:
  Public:
    - /api/v1/daily-ca/today/ → 200 with articles
    - /api/v1/daily-ca/<date>/ → 200 with articles for date
    - /api/v1/daily-ca/article/<slug>/ → 200 full detail with concept_links
    - /api/v1/daily-ca/article/<slug>/ → 404 for unknown slug
    - /api/v1/daily-ca/archive/ → 200 with date-grouped data
    - Unpublished articles NOT returned in public endpoints

  Admin (no auth):
    - GET /api/v1/admin/daily-ca/proposals/<date>/ → 200 list
    - POST /api/v1/admin/daily-ca/proposals/approve/ → 200, updates status
    - POST approve/ validates max 10 → 400 when >10
    - GET /api/v1/admin/daily-ca/generate/status/ → 200 breakdown
    - POST /api/v1/admin/daily-ca/publish/<date>/ → 200, sets is_published
    - GET /api/v1/admin/daily-ca/articles/<date>/ → 200 incl. unpublished
"""

import uuid
from datetime import date

import pytest
from django.test import Client

from engines.daily_ca.models import CaDailyProposal, DailyCaArticle
from engines.tags.models import ConceptArticleLink, ConceptPage


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def published_article():
    article = DailyCaArticle.objects.create(
        title="Published Test Article",
        slug="2099-04-10-published-test-article",
        subject_name="Polity",
        gs_paper="GS2",
        published_date=date(2099, 4, 10),
        body_md="This is the raw body with [[Article 370]] concept.",
        body_md_processed="This is processed with [Article 370](/concepts/article-370).",
        news_context="Some news.",
        is_published=True,
        order_on_date=1,
    )
    return article


@pytest.fixture
def unpublished_article():
    return DailyCaArticle.objects.create(
        title="Unpublished Article",
        slug="2099-04-10-unpublished-article",
        subject_name="Economy",
        published_date=date(2099, 4, 10),
        body_md="Unpublished content.",
        is_published=False,
    )


@pytest.fixture
def sample_proposal():
    return CaDailyProposal.objects.create(
        date=date(2099, 4, 10),
        title="Test Proposal",
        description="Description of news.",
        subject_name="Polity",
        gs_paper="GS2",
        status="pending",
        relevance_score=8.5,
    )


# ── Public Views ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTodayView:
    def test_returns_200(self, client, published_article):
        # Published article has published_date=2099-04-10
        # We need today's date to match — mock timezone.now
        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "engines.daily_ca.views.timezone.now",
                lambda: __import__("datetime").datetime(2099, 4, 10, 12, 0),
            )
            resp = client.get("/api/v1/daily-ca/today/")
        assert resp.status_code == 200

    def test_response_structure(self, client):
        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "engines.daily_ca.views.timezone.now",
                lambda: __import__("datetime").datetime(2099, 4, 10, 12, 0),
            )
            resp = client.get("/api/v1/daily-ca/today/")
        data = resp.json()
        assert "date" in data
        assert "count" in data
        assert "articles" in data

    def test_unpublished_not_returned(self, client, unpublished_article):
        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "engines.daily_ca.views.timezone.now",
                lambda: __import__("datetime").datetime(2099, 4, 10, 12, 0),
            )
            resp = client.get("/api/v1/daily-ca/today/")
        slugs = [a["slug"] for a in resp.json()["articles"]]
        assert "2099-04-10-unpublished-article" not in slugs


@pytest.mark.django_db
class TestDateView:
    def test_valid_date_returns_200(self, client, published_article):
        resp = client.get("/api/v1/daily-ca/2099-04-10/")
        assert resp.status_code == 200

    def test_invalid_date_returns_400(self, client):
        resp = client.get("/api/v1/daily-ca/not-a-date/")
        assert resp.status_code == 400

    def test_returns_only_published(
        self, client, published_article, unpublished_article
    ):
        resp = client.get("/api/v1/daily-ca/2099-04-10/")
        slugs = [a["slug"] for a in resp.json()["articles"]]
        assert "2099-04-10-published-test-article" in slugs
        assert "2099-04-10-unpublished-article" not in slugs

    def test_empty_date_returns_empty_list(self, client):
        resp = client.get("/api/v1/daily-ca/2020-01-01/")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


@pytest.mark.django_db
class TestArticleDetailView:
    def test_published_article_returns_200(self, client, published_article):
        resp = client.get(f"/api/v1/daily-ca/article/{published_article.slug}/")
        assert resp.status_code == 200

    def test_unknown_slug_returns_404(self, client):
        resp = client.get("/api/v1/daily-ca/article/does-not-exist/")
        assert resp.status_code == 404

    def test_unpublished_returns_404(self, client, unpublished_article):
        resp = client.get(f"/api/v1/daily-ca/article/{unpublished_article.slug}/")
        assert resp.status_code == 404

    def test_concept_links_in_response(self, client, published_article):
        concept = ConceptPage.objects.create(name="Article 370", slug="article-370")
        ConceptArticleLink.objects.create(
            concept_page=concept,
            daily_ca_article_id=published_article.id,
        )
        resp = client.get(f"/api/v1/daily-ca/article/{published_article.slug}/")
        data = resp.json()
        assert "concept_links" in data
        concept_slugs = [c["slug"] for c in data["concept_links"]]
        assert "article-370" in concept_slugs

    def test_body_md_processed_returned(self, client, published_article):
        resp = client.get(f"/api/v1/daily-ca/article/{published_article.slug}/")
        data = resp.json()
        assert "body_md_processed" in data
        assert "/concepts/article-370" in data["body_md_processed"]


@pytest.mark.django_db
class TestArchiveView:
    def test_returns_200(self, client, published_article):
        resp = client.get("/api/v1/daily-ca/archive/")
        assert resp.status_code == 200

    def test_response_has_archive_key(self, client):
        resp = client.get("/api/v1/daily-ca/archive/")
        assert "archive" in resp.json()


# ── Admin Views ───────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAdminProposalListView:
    def test_returns_200(self, client, sample_proposal):
        resp = client.get("/api/v1/admin/daily-ca/proposals/2099-04-10/")
        assert resp.status_code == 200

    def test_returns_proposals(self, client, sample_proposal):
        resp = client.get("/api/v1/admin/daily-ca/proposals/2099-04-10/")
        data = resp.json()
        assert data["count"] >= 1
        assert data["proposals"][0]["title"] == "Test Proposal"

    def test_invalid_date_returns_400(self, client):
        resp = client.get("/api/v1/admin/daily-ca/proposals/bad-date/")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestAdminApproveView:
    def test_approve_pending_proposals(self, client, sample_proposal):
        resp = client.post(
            "/api/v1/admin/daily-ca/proposals/approve/",
            data={"proposal_ids": [str(sample_proposal.id)]},
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.json()["approved"] == 1
        sample_proposal.refresh_from_db()
        assert sample_proposal.status == "approved"

    def test_max_10_enforced(self, client):
        ids = [str(uuid.uuid4()) for _ in range(11)]
        resp = client.post(
            "/api/v1/admin/daily-ca/proposals/approve/",
            data={"proposal_ids": ids},
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "Max 10" in resp.json()["error"]

    def test_missing_proposal_ids_returns_400(self, client):
        resp = client.post(
            "/api/v1/admin/daily-ca/proposals/approve/",
            data={},
            content_type="application/json",
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestAdminGenerateStatusView:
    def test_returns_200(self, client, sample_proposal):
        resp = client.get("/api/v1/admin/daily-ca/generate/status/?date=2099-04-10")
        assert resp.status_code == 200

    def test_status_breakdown_present(self, client, sample_proposal):
        resp = client.get("/api/v1/admin/daily-ca/generate/status/?date=2099-04-10")
        data = resp.json()
        assert "status_breakdown" in data
        assert "total" in data
        assert data["total"] >= 1


@pytest.mark.django_db
class TestAdminPublishDateView:
    def test_publishes_all_generated_articles(self, client, unpublished_article):
        resp = client.post("/api/v1/admin/daily-ca/publish/2099-04-10/")
        assert resp.status_code == 200
        assert resp.json()["published"] >= 1
        unpublished_article.refresh_from_db()
        assert unpublished_article.is_published is True

    def test_invalid_date_returns_400(self, client):
        resp = client.post("/api/v1/admin/daily-ca/publish/bad-date/")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestAdminArticlesDateView:
    def test_returns_all_including_unpublished(
        self, client, published_article, unpublished_article
    ):
        resp = client.get("/api/v1/admin/daily-ca/articles/2099-04-10/")
        assert resp.status_code == 200
        slugs = [a["slug"] for a in resp.json()["articles"]]
        assert "2099-04-10-published-test-article" in slugs
        assert "2099-04-10-unpublished-article" in slugs

    def test_invalid_date_returns_400(self, client):
        resp = client.get("/api/v1/admin/daily-ca/articles/bad-date/")
        assert resp.status_code == 400
