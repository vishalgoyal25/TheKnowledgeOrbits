"""Knowledge Engine - Service Tests"""

from unittest.mock import patch

import pytest

from engines.content.models import Chunk, Document, Embedding
from engines.knowledge.models import Module, Program, Subject, Topic
from engines.knowledge.services.mapping_service import MappingService


@pytest.fixture
def hierarchy():
    """Create knowledge hierarchy."""
    program = Program.objects.create(name="UPSC CSE")
    subject = Subject.objects.create(name="Polity", program=program)
    module = Module.objects.create(name="Constitution", subject=subject)
    topic = Topic.objects.create(
        name="Article 370",
        module=module,
        subject=subject,
        description="Article 370 special status",
    )
    return topic


@pytest.fixture
def chunks():
    """Create test chunks with embeddings."""
    doc = Document.objects.create(
        title="Test Doc", file_path="/test.pdf", source_type="static"
    )

    chunks_data = []
    for i in range(3):
        chunk = Chunk.objects.create(
            chunk_text=f"Test content {i}",
            chunk_index=i,
            source_type="static",
            document=doc,
        )

        # Create embedding
        Embedding.objects.create(
            content_type="chunk", content_id=chunk.id, vector=[0.1 * i] * 384
        )

        chunks_data.append(chunk)

    return chunks_data


@pytest.mark.django_db
class TestMappingService:
    @patch(
        "engines.content.services.embedding_service.EmbeddingService.generate_embedding"
    )
    def test_auto_suggest_chunks(self, mock_embedding, hierarchy, chunks):
        """Test auto-suggest chunks for topic."""
        mock_embedding.return_value = [0.5] * 384

        suggestions = MappingService.auto_suggest_chunks(
            topic_id=str(hierarchy.id), limit=10
        )

        assert isinstance(suggestions, list)

    def test_cosine_similarity(self):
        """Test cosine similarity calculation."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        similarity = MappingService._cosine_similarity(vec1, vec2)
        assert similarity == 0.0

        vec3 = [1.0, 0.0, 0.0]
        vec4 = [1.0, 0.0, 0.0]

        similarity = MappingService._cosine_similarity(vec3, vec4)
        assert similarity == 1.0


# ══════════════════════════════════════════════════════════════════════════════
# SearchService
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSearchServiceLimit:
    """Tests for SearchService.semantic_search — limit and cap behaviour."""

    @patch(
        "engines.knowledge.services.search_service.EmbeddingService.generate_embedding",
        return_value=[0.5] * 384,
    )
    def test_returns_list(self, _mock_emb):
        """semantic_search always returns a list (never raises)."""
        from engines.knowledge.services.search_service import SearchService

        result = SearchService.semantic_search(query="polity", limit=5)
        assert isinstance(result, list)

    @patch(
        "engines.knowledge.services.search_service.EmbeddingService.generate_embedding",
        return_value=[0.5] * 384,
    )
    def test_result_count_does_not_exceed_limit(self, _mock_emb):
        """Number of results must never exceed the requested limit."""
        from engines.knowledge.services.search_service import SearchService

        result = SearchService.semantic_search(query="constitution", limit=3)
        assert len(result) <= 3

    @patch(
        "engines.knowledge.services.search_service.EmbeddingService.generate_embedding",
        side_effect=Exception("HF down"),
    )
    def test_returns_empty_list_on_embedding_failure(self, _mock_emb):
        """If embedding generation fails, semantic_search returns [] not an exception."""
        from engines.knowledge.services.search_service import SearchService

        result = SearchService.semantic_search(query="economy", limit=10)
        assert result == []

    def test_default_limit_is_50(self):
        """semantic_search default limit parameter value is 50."""
        import inspect
        from engines.knowledge.services.search_service import SearchService

        sig = inspect.signature(SearchService.semantic_search)
        assert sig.parameters["limit"].default == 50


@pytest.mark.django_db
class TestSearchServiceDailyCa:
    """Tests for _daily_ca_article_search — Feature 2 keyword search."""

    def _make_daily_ca_article(self, title: str, published: bool = True):
        import uuid
        from datetime import date
        from engines.daily_ca.models import DailyCaArticle

        return DailyCaArticle.objects.create(
            title=title,
            slug=f"2026-04-22-{uuid.uuid4().hex[:6]}",
            published_date=date(2026, 4, 22),
            body_md="Some content.",
            news_context=f"News context about {title}.",
            is_published=published,
        )

    def test_returns_published_articles_matching_title(self):
        """Published articles matching the query title are returned."""
        from engines.knowledge.services.search_service import SearchService

        self._make_daily_ca_article("RBI Monetary Policy 2026", published=True)

        results = SearchService._daily_ca_article_search("RBI Monetary", existing=[])
        assert any("RBI Monetary" in r["title"] for r in results)

    def test_excludes_unpublished_articles(self):
        """Unpublished drafts must never appear in search results."""
        from engines.knowledge.services.search_service import SearchService

        self._make_daily_ca_article("Draft Article GST Reform", published=False)

        results = SearchService._daily_ca_article_search("GST Reform", existing=[])
        assert all("Draft Article" not in r["title"] for r in results)

    def test_excludes_already_existing_results(self):
        """Articles already in the existing list must be skipped (dedup)."""
        from engines.knowledge.services.search_service import SearchService

        article = self._make_daily_ca_article("ISRO Chandrayaan 2026", published=True)

        existing = [
            {
                "id": str(article.id),
                "type": "current_affair",
                "title": "ISRO Chandrayaan 2026",
            }
        ]
        results = SearchService._daily_ca_article_search(
            "Chandrayaan", existing=existing
        )

        assert all(r["id"] != str(article.id) for r in results)

    def test_result_type_is_current_affair(self):
        """Daily CA articles must be returned with type='current_affair'."""
        from engines.knowledge.services.search_service import SearchService

        self._make_daily_ca_article("Parliament Budget Session", published=True)

        results = SearchService._daily_ca_article_search("Budget Session", existing=[])
        assert all(r["type"] == "current_affair" for r in results)

    def test_result_url_uses_daily_ca_slug(self):
        """URL must point to /daily-ca/article/{slug}."""
        from engines.knowledge.services.search_service import SearchService

        self._make_daily_ca_article("Electoral Bonds Verdict", published=True)

        results = SearchService._daily_ca_article_search("Electoral Bonds", existing=[])
        assert all(r["url"].startswith("/daily-ca/article/") for r in results)
