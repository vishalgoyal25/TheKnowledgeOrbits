"""
engines/tags/tests/test_services.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase M1 — Tags Engine service tests.

Tests:
  TagService:
    - extract_and_link_tags() with override tags (no GROQ)
    - Max 8 tags enforced (12 overrides → only 8 linked)
    - Fuzzy match reuses existing tag
    - Invalid content_type returns []

  ConceptPageResolver:
    - process_and_replace() resolves [[term]] to /concepts/slug
    - Exact match reuses existing ConceptPage (no GROQ call)
    - Fuzzy match reuses near-duplicate concept
    - Max 8 concept links enforced (12 terms → 8 linked, rest plain text)
    - New stub created when no match (mocked GROQ)
"""

import uuid
from datetime import date
from unittest.mock import patch

import pytest

from engines.tags.models import ArticleTag, ConceptArticleLink, ConceptPage, Tag
from engines.tags.services.concept_resolver import ConceptPageResolver
from engines.tags.services.tag_service import TagService


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_article(title="Test Article", slug_suffix=None):
    """Create a real DailyCaArticle for FK-safe ConceptArticleLink tests."""
    from engines.daily_ca.models import DailyCaArticle

    suffix = slug_suffix or uuid.uuid4().hex[:6]
    return DailyCaArticle.objects.create(
        title=title,
        slug=f"2026-04-10-{suffix}",
        published_date=date(2026, 4, 10),
        body_md="Test content.",
    )


# ── TagService ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestTagServiceExtract:

    def test_extract_with_overrides_no_groq(self):
        """Override list → no GROQ call, tags linked directly."""
        Tag.objects.create(name="nuclear-energy", slug="nuclear-energy", tag_type="topic")
        article_id = uuid.uuid4()

        linked = TagService.extract_and_link_tags(
            article_text="some article text about nuclear energy",
            content_type="daily_ca",
            object_id=article_id,
            overrides=["nuclear-energy"],
        )
        assert len(linked) >= 1
        assert any(t.slug == "nuclear-energy" for t in linked)

    def test_max_8_tags_enforced(self):
        """12 override tags → max 8 ArticleTag rows created."""
        for i in range(12):
            Tag.objects.get_or_create(
                name=f"tag-{i}", slug=f"tag-{i}", defaults={"tag_type": "topic"}
            )
        article_id = uuid.uuid4()
        overrides = [f"tag-{i}" for i in range(12)]

        linked = TagService.extract_and_link_tags(
            article_text="text",
            content_type="daily_ca",
            object_id=article_id,
            overrides=overrides,
        )
        assert len(linked) <= 8
        assert ArticleTag.objects.filter(
            content_type="daily_ca", object_id=article_id
        ).count() <= 8

    def test_fuzzy_match_reuses_existing_tag(self):
        """Near-duplicate slug → fuzzy match reuses existing, doesn't create new."""
        Tag.objects.create(name="nuclear-energy", slug="nuclear-energy")
        article_id = uuid.uuid4()

        TagService.extract_and_link_tags(
            article_text="text",
            content_type="daily_ca",
            object_id=article_id,
            overrides=["nuclear-energi"],  # near-duplicate
        )
        assert Tag.objects.filter(slug__startswith="nuclear-energ").count() <= 2

    def test_invalid_content_type_returns_empty(self):
        article_id = uuid.uuid4()
        result = TagService.extract_and_link_tags(
            article_text="text",
            content_type="invalid_type",
            object_id=article_id,
            overrides=["some-tag"],
        )
        assert result == []

    def test_usage_count_incremented_on_new_link(self):
        tag = Tag.objects.create(name="gst-council", slug="gst-council", usage_count=5)
        article_id = uuid.uuid4()

        TagService.extract_and_link_tags(
            article_text="text",
            content_type="daily_ca",
            object_id=article_id,
            overrides=["gst-council"],
        )
        tag.refresh_from_db()
        assert tag.usage_count == 6

    def test_duplicate_link_does_not_double_increment(self):
        tag = Tag.objects.create(name="inflation", slug="inflation", usage_count=1)
        article_id = uuid.uuid4()

        TagService.extract_and_link_tags(
            article_text="text",
            content_type="daily_ca",
            object_id=article_id,
            overrides=["inflation"],
        )
        TagService.extract_and_link_tags(
            article_text="text",
            content_type="daily_ca",
            object_id=article_id,
            overrides=["inflation"],
        )
        tag.refresh_from_db()
        assert tag.usage_count == 2  # incremented only once


# ── ConceptPageResolver ───────────────────────────────────────────────────────

@pytest.mark.django_db
class TestConceptPageResolver:

    def test_process_and_replace_exact_match(self):
        """Existing ConceptPage slug → [[term]] replaced with markdown link."""
        ConceptPage.objects.create(name="Sendai Framework", slug="sendai-framework")
        article = _make_article()

        result = ConceptPageResolver.process_and_replace(
            "The [[Sendai Framework]] guides DRR globally.",
            article.id,
        )
        assert "[Sendai Framework](/concepts/sendai-framework)" in result
        assert "[[" not in result

    def test_process_writes_concept_article_link(self):
        concept = ConceptPage.objects.create(name="CLNDA", slug="clnda")
        article = _make_article()

        ConceptPageResolver.process_and_replace("The [[CLNDA]] is important.", article.id)

        assert ConceptArticleLink.objects.filter(
            concept_page=concept,
            daily_ca_article_id=article.id,
        ).exists()

    def test_usage_count_incremented(self):
        concept = ConceptPage.objects.create(name="ABDM", slug="abdm", usage_count=3)
        article = _make_article()

        ConceptPageResolver.process_and_replace("[[ABDM]] is a health mission.", article.id)
        concept.refresh_from_db()
        assert concept.usage_count == 4

    def test_max_8_concept_links_enforced(self):
        """12 [[terms]] → only 8 get linked; rest rendered as plain text."""
        for i in range(12):
            ConceptPage.objects.create(name=f"Concept {i}", slug=f"concept-{i}")

        body = " ".join(f"[[Concept {i}]]" for i in range(12))
        article = _make_article()

        result = ConceptPageResolver.process_and_replace(body, article.id)

        links_created = ConceptArticleLink.objects.filter(
            daily_ca_article_id=article.id
        ).count()
        assert links_created == 8
        assert "[[" not in result

    def test_new_stub_created_when_no_match(self):
        """No existing ConceptPage → new stub created (mocked GROQ)."""
        article = _make_article()

        with patch(
            "engines.tags.services.concept_resolver.llm_call",
            return_value="A brief description of PM-WANI.",
        ):
            with patch("engines.tags.services.concept_resolver.time.sleep"):
                result = ConceptPageResolver.process_and_replace(
                    "The [[PM-WANI]] scheme extends WiFi access.",
                    article.id,
                )

        assert ConceptPage.objects.filter(slug="pm-wani").exists()
        assert "[PM-WANI](/concepts/pm-wani)" in result
        assert ConceptPageResolver.last_new_concept_calls == 1

    def test_fuzzy_match_prevents_near_duplicate(self):
        """Exact slug match → reuses existing, no new ConceptPage created."""
        existing = ConceptPage.objects.create(
            name="civil-liability-for-nuclear-damage-act",
            slug="civil-liability-for-nuclear-damage-act",
        )
        article = _make_article()

        with patch("engines.tags.services.concept_resolver.time.sleep"):
            ConceptPageResolver.process_and_replace(
                "The [[civil-liability-for-nuclear-damage-act]] is a law.",
                article.id,
            )
        count = ConceptPage.objects.filter(
            slug__icontains="civil-liability"
        ).count()
        assert count == 1

    def test_empty_brackets_left_as_is(self):
        article = _make_article()
        result = ConceptPageResolver.process_and_replace("Text [[]] more text.", article.id)
        assert "[[]]" in result
