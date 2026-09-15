"""
engines/tags/tests/test_concept_seo.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
G3.3 — the ONE definition of "indexable" for concept pages, and the sitemap
feed that applies it. Pins the G0.3 verdict (§4.3): list a concept only when
its body has >= 400 words AND >= 3 headings. `is_content_ready` alone admits
a 28-word page and must never be the gate.
"""

from django.core.cache import cache

from rest_framework import status
from rest_framework.test import APIClient

import pytest

from engines.tags.models import ConceptPage
from engines.tags.services.concept_seo_service import is_indexable

RICH_BODY = "\n\n".join(
    ["## Section " + str(i) + "\n\n" + ("word " * 150) for i in range(3)]
)  # 3 headings, ~450 words


def _concept(slug: str, body: str = "", ready: bool = True) -> ConceptPage:
    return ConceptPage.objects.create(
        name=slug.replace("-", " ").title(),
        slug=slug,
        brief_description="brief",
        body_md=body,
        is_content_ready=ready,
    )


@pytest.mark.django_db
class TestIsIndexable:
    def test_rich_page_is_indexable(self):
        assert is_indexable(_concept("rich", RICH_BODY)) is True

    def test_stub_is_not(self):
        assert is_indexable(_concept("stub", "", ready=False)) is False

    def test_ready_flag_alone_is_not_enough(self):
        """The 28-word 'ready' page from the audit must fail."""
        assert is_indexable(_concept("thin", "word " * 28, ready=True)) is False

    def test_long_but_unstructured_is_not(self):
        """600 words, zero headings — the wall-of-text shape, 474 rows on 09-14."""
        assert is_indexable(_concept("wall", "word " * 600)) is False

    def test_short_but_structured_is_not(self):
        body = "## A\n\ntext\n\n## B\n\ntext\n\n## C\n\ntext"
        assert is_indexable(_concept("short", body)) is False


@pytest.mark.django_db
class TestConceptSitemapFeed:
    @pytest.fixture(autouse=True)
    def _clear(self):
        cache.clear()
        yield
        cache.clear()

    def test_feed_lists_only_indexable_slugs_with_lastmod(self):
        _concept("rich-one", RICH_BODY)
        _concept("thin-one", "word " * 28)
        _concept("stub-one", "", ready=False)

        response = APIClient().get("/api/v1/concepts/sitemap/")

        assert response.status_code == status.HTTP_200_OK
        slugs = [row["slug"] for row in response.data]
        assert slugs == ["rich-one"]
        assert "lastmod" in response.data[0]

    def test_detail_payload_carries_is_indexable(self):
        _concept("rich-two", RICH_BODY)
        _concept("thin-two", "word " * 28)

        client = APIClient()
        assert client.get("/api/v1/concepts/rich-two/").data["is_indexable"] is True
        assert client.get("/api/v1/concepts/thin-two/").data["is_indexable"] is False
