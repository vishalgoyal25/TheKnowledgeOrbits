"""
engines/tags/tests/test_models.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase M1 — Tags Engine model tests.

Tests:
  - Tag creation with all 10 tag_types
  - Slug uniqueness constraint
  - usage_count default = 0
  - Tag unique name constraint
  - ConceptPage creation with is_content_ready=False
  - ConceptPage stub fields
  - ConceptArticleLink unique constraint
  - ArticleTag unique constraint
"""

import uuid

import pytest
from django.db import IntegrityError

from engines.tags.models import (
    ArticleTag,
    ConceptArticleLink,
    ConceptPage,
    Tag,
)


@pytest.mark.django_db
class TestTagModel:

    def test_create_tag_all_types(self):
        types = [
            "topic", "subtopic", "scheme", "person", "place",
            "organisation", "concept", "law", "event", "other",
        ]
        for i, tag_type in enumerate(types):
            tag = Tag.objects.create(
                name=f"test-tag-{i}",
                slug=f"test-tag-{i}",
                tag_type=tag_type,
            )
            assert tag.tag_type == tag_type

    def test_tag_usage_count_default_zero(self):
        tag = Tag.objects.create(name="nuclear-energy", slug="nuclear-energy")
        assert tag.usage_count == 0

    def test_tag_is_active_default_true(self):
        tag = Tag.objects.create(name="active-tag", slug="active-tag")
        assert tag.is_active is True

    def test_tag_unique_name_constraint(self):
        Tag.objects.create(name="duplicate-tag", slug="duplicate-tag")
        with pytest.raises(IntegrityError):
            Tag.objects.create(name="duplicate-tag", slug="duplicate-tag-2")

    def test_tag_unique_slug_constraint(self):
        Tag.objects.create(name="tag-one", slug="same-slug")
        with pytest.raises(IntegrityError):
            Tag.objects.create(name="tag-two", slug="same-slug")

    def test_tag_str(self):
        tag = Tag.objects.create(name="article-370", slug="article-370", tag_type="law")
        assert "article-370" in str(tag)
        assert "law" in str(tag)


@pytest.mark.django_db
class TestConceptPageModel:

    def test_concept_page_default_not_ready(self):
        concept = ConceptPage.objects.create(
            name="Viksit Bharat 2047",
            slug="viksit-bharat-2047",
        )
        assert concept.is_content_ready is False

    def test_concept_page_body_md_empty_by_default(self):
        concept = ConceptPage.objects.create(name="ABDM", slug="abdm")
        assert concept.body_md == ""

    def test_concept_page_usage_count_default_zero(self):
        concept = ConceptPage.objects.create(name="PM-WANI", slug="pm-wani")
        assert concept.usage_count == 0

    def test_concept_page_str(self):
        concept = ConceptPage.objects.create(name="Sendai Framework", slug="sendai-framework")
        assert "Sendai Framework" in str(concept)
        assert "stub" in str(concept)

    def test_concept_page_str_full_when_ready(self):
        concept = ConceptPage.objects.create(
            name="CLNDA", slug="clnda", is_content_ready=True
        )
        assert "full" in str(concept)


@pytest.mark.django_db
class TestConceptArticleLinkModel:

    def test_concept_article_link_unique_constraint(self):
        concept = ConceptPage.objects.create(name="Test Concept", slug="test-concept")
        article_id = uuid.uuid4()
        ConceptArticleLink.objects.create(
            concept_page=concept,
            daily_ca_article_id=article_id,
        )
        with pytest.raises(IntegrityError):
            ConceptArticleLink.objects.create(
                concept_page=concept,
                daily_ca_article_id=article_id,
            )


@pytest.mark.django_db
class TestArticleTagModel:

    def test_article_tag_unique_constraint(self):
        tag = Tag.objects.create(name="pm-kisan", slug="pm-kisan")
        obj_id = uuid.uuid4()
        ArticleTag.objects.create(
            tag=tag,
            content_type="daily_ca",
            object_id=obj_id,
            relevance=1.0,
        )
        with pytest.raises(IntegrityError):
            ArticleTag.objects.create(
                tag=tag,
                content_type="daily_ca",
                object_id=obj_id,
                relevance=0.5,
            )

    def test_article_tag_str(self):
        tag = Tag.objects.create(name="gst", slug="gst")
        obj_id = uuid.uuid4()
        at = ArticleTag.objects.create(
            tag=tag,
            content_type="daily_ca",
            object_id=obj_id,
        )
        assert "gst" in str(at)
        assert "daily_ca" in str(at)
