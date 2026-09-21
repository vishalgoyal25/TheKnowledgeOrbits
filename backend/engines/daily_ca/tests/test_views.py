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


@pytest.mark.django_db
class TestSitemapEntriesView:
    """G3.3 — every PUBLISHED article's slug + lastmod, unpaginated, nothing else."""

    def test_lists_published_only(self, client, published_article, unpublished_article):
        from django.core.cache import cache

        cache.clear()
        resp = client.get("/api/v1/daily-ca/sitemap/")
        cache.clear()

        assert resp.status_code == 200
        rows = resp.json()
        assert [r["slug"] for r in rows] == ["2099-04-10-published-test-article"]
        assert set(rows[0]) == {"slug", "lastmod"}

    def test_literal_segment_wins_over_date_route(self, client):
        """'sitemap' must never be parsed as a <date_str>."""
        from django.core.cache import cache

        cache.clear()
        resp = client.get("/api/v1/daily-ca/sitemap/")
        cache.clear()

        assert resp.status_code == 200
        assert resp.json() == []


# ── G3.14a — syllabus ⇄ daily-CA links ────────────────────────────────────────


@pytest.fixture
def syllabus_tree():
    """Subject › two modules › a topic with one subtopic, and a topic elsewhere."""
    from engines.knowledge.models import Module, Program, Subject, Topic

    program = Program.objects.create(name="P", description="p")
    subject = Subject.objects.create(name="Polity", program=program, order_index=0)
    module = Module.objects.create(name="Constitution", subject=subject, order_index=0)
    other_module = Module.objects.create(
        name="Parliament", subject=subject, order_index=1
    )
    topic = Topic.objects.create(
        name="Fundamental Rights", module=module, subject=subject, order_index=0
    )
    subtopic = Topic.objects.create(
        name="Right to Equality",
        module=module,
        subject=subject,
        parent_topic=topic,
        node_type="subtopic",
        order_index=0,
    )
    other_topic = Topic.objects.create(
        name="Lok Sabha", module=other_module, subject=subject, order_index=0
    )
    return {
        "subject": subject,
        "module": module,
        "other_module": other_module,
        "topic": topic,
        "subtopic": subtopic,
        "other_topic": other_topic,
    }


def _ca(topic, day: int, order: int = 1, published: bool = True) -> DailyCaArticle:
    return DailyCaArticle.objects.create(
        title=f"Article {day}-{order}",
        slug=f"2099-05-{day:02d}-article-{order}-{uuid.uuid4().hex[:6]}",
        topic=topic,
        subject_name="Polity",
        gs_paper="GS2",
        published_date=date(2099, 5, day),
        body_md="Body.",
        is_published=published,
        order_on_date=order,
    )


@pytest.mark.django_db
class TestSyllabusBlock:
    """The detail payload says where the article sits in the syllabus, as links."""

    def test_null_when_the_article_has_no_topic(self, client, published_article):
        resp = client.get(f"/api/v1/daily-ca/article/{published_article.slug}/")
        assert resp.status_code == 200
        assert resp.json()["syllabus"] is None

    def test_trail_and_has_content(self, client, syllabus_tree):
        from engines.book_content.models import BookContent

        t = syllabus_tree
        article = _ca(t["topic"], day=10)

        data = client.get(f"/api/v1/daily-ca/article/{article.slug}/").json()
        block = data["syllabus"]
        assert block["topic"] == {
            "id": str(t["topic"].id),
            "slug": t["topic"].slug,
            "name": "Fundamental Rights",
            "has_content": False,
        }
        assert block["module"] == {
            "id": str(t["module"].id),
            "slug": t["module"].slug,
            "name": "Constitution",
        }
        assert block["subject"] == {
            "id": str(t["subject"].id),
            "slug": t["subject"].slug,
            "name": "Polity",
        }
        assert block["topic"]["slug"], "slugs are minted on create (G3.10)"

        BookContent.objects.create(
            topic=t["topic"], subject=t["subject"], content_markdown="## Intro\n\nText."
        )
        data = client.get(f"/api/v1/daily-ca/article/{article.slug}/").json()
        assert data["syllabus"]["topic"]["has_content"] is True


@pytest.mark.django_db
class TestByNodeView:
    """
    GET /daily-ca/by-node/<uuid>/?scope=… — the reverse direction, pure FK
    matching: many articles → one node; a parent topic sees its subtopics'
    articles; the same article appears under its topic, module and subject.
    """

    @pytest.fixture(autouse=True)
    def _no_cache(self):
        from django.core.cache import cache

        cache.clear()
        yield
        cache.clear()

    def _get(self, client, node_id, **params):
        return client.get(f"/api/v1/daily-ca/by-node/{node_id}/", params)

    def test_topic_scope_rolls_up_subtopics_published_only_newest_first(
        self, client, syllabus_tree
    ):
        t = syllabus_tree
        on_topic = _ca(t["topic"], day=10)
        on_subtopic = _ca(t["subtopic"], day=11)
        _ca(t["topic"], day=12, published=False)
        _ca(t["other_topic"], day=13)  # another module — not this topic's

        resp = self._get(client, t["topic"].id, scope="topic")
        assert resp.status_code == 200
        body = resp.json()
        assert [a["slug"] for a in body["articles"]] == [
            on_subtopic.slug,
            on_topic.slug,
        ]
        assert body["count"] == 2 and body["has_more"] is False
        assert body["scope"] == "topic" and body["node_id"] == str(t["topic"].id)

    def test_subtopic_scope_sees_only_itself(self, client, syllabus_tree):
        t = syllabus_tree
        _ca(t["topic"], day=10)
        mine = _ca(t["subtopic"], day=11)

        body = self._get(client, t["subtopic"].id, scope="topic").json()
        assert [a["slug"] for a in body["articles"]] == [mine.slug]

    def test_module_and_subject_scopes(self, client, syllabus_tree):
        t = syllabus_tree
        a = _ca(t["topic"], day=10)
        b = _ca(t["subtopic"], day=11)
        d = _ca(t["other_topic"], day=13)

        module = self._get(client, t["module"].id, scope="module").json()
        assert {x["slug"] for x in module["articles"]} == {a.slug, b.slug}

        subject = self._get(client, t["subject"].id, scope="subject").json()
        assert [x["slug"] for x in subject["articles"]] == [d.slug, b.slug, a.slug]

    def test_scope_defaults_to_topic(self, client, syllabus_tree):
        t = syllabus_tree
        a = _ca(t["topic"], day=10)
        body = self._get(client, t["topic"].id).json()
        assert [x["slug"] for x in body["articles"]] == [a.slug]

    def test_pagination_limit_offset_has_more(self, client, syllabus_tree):
        t = syllabus_tree
        for day in range(1, 13):  # 12 articles, days 1..12
            _ca(t["topic"], day=day)

        page1 = self._get(client, t["topic"].id, limit=5, offset=0).json()
        assert len(page1["articles"]) == 5
        assert page1["count"] == 12 and page1["has_more"] is True
        assert page1["articles"][0]["published_date"] == "2099-05-12"

        page3 = self._get(client, t["topic"].id, limit=5, offset=10).json()
        assert len(page3["articles"]) == 2 and page3["has_more"] is False

        capped = self._get(client, t["topic"].id, limit=100).json()
        assert capped["limit"] == 30 and len(capped["articles"]) == 12

        junk = self._get(client, t["topic"].id, limit="x", offset="-5").json()
        assert junk["limit"] == 10 and junk["offset"] == 0

    def test_unknown_node_is_an_empty_page_not_a_404(self, client):
        resp = self._get(client, uuid.uuid4(), scope="module")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0 and resp.json()["articles"] == []

    def test_bad_scope_is_400(self, client, syllabus_tree):
        resp = self._get(client, syllabus_tree["topic"].id, scope="program")
        assert resp.status_code == 400

    def test_list_shape_carries_what_the_card_needs(self, client, syllabus_tree):
        t = syllabus_tree
        _ca(t["topic"], day=10)
        item = self._get(client, t["topic"].id).json()["articles"][0]
        for key in ("slug", "title", "published_date", "gs_paper", "hero_image_url"):
            assert key in item
        assert "body_md_processed" not in item, "list serializer — no bodies"


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
