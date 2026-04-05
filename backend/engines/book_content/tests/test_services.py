"""
engines/book_content/tests/test_services.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase H — Service Unit Tests

ALL service tests use unittest.mock.patch — ZERO real LLM calls, ZERO external HTTP.
DB tests (smart skip) use Django's TestCase with mocked external services only.

Covers:
  - llm_service.llm_call()
  - wiki_service.fetch_full_page() + extract_relevant_section()
  - book_planner_service.generate_book_plan()
  - quality_engine_service.generate_quality_article()
  - ingestor_service smart skip: existing BookContent → skips LLM generation
"""

from __future__ import annotations

import json
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from django.test import TestCase


# ─────────────────────────────────────────────────────────────────────────────
# LLM SERVICE
# ─────────────────────────────────────────────────────────────────────────────


class TestLlmService(unittest.TestCase):
    """Tests for engines.book_content.services.llm_service.llm_call"""

    @patch("engines.book_content.services.llm_service.time.sleep", return_value=None)
    def test_llm_call_returns_stripped_string_on_success(
        self, _mock_sleep: MagicMock
    ) -> None:
        """llm_call() returns stripped content string from the GROQ response."""
        mock_response = MagicMock()
        mock_response.content = "  Article content here.  "
        mock_client = MagicMock()
        mock_client.invoke.return_value = mock_response

        with patch(
            "engines.book_content.services.llm_service._pool_standard",
            [mock_client],
        ):
            from engines.book_content.services.llm_service import llm_call

            result = llm_call("Test prompt", mode="standard")

        assert isinstance(result, str)
        assert result == "Article content here."
        mock_client.invoke.assert_called_once_with("Test prompt")

    @patch("engines.book_content.services.llm_service.time.sleep", return_value=None)
    def test_llm_call_returns_empty_string_after_all_retries_exhausted(
        self, _mock_sleep: MagicMock
    ) -> None:
        """llm_call() returns '' when every key and every retry fails."""
        mock_client = MagicMock()
        mock_client.invoke.side_effect = Exception("Rate limit exceeded")

        with (
            patch(
                "engines.book_content.services.llm_service._pool_standard",
                [mock_client],
            ),
            patch(
                "engines.book_content.services.llm_service._pool_writer",
                [mock_client],
            ),
            patch(
                "engines.book_content.services.llm_service._pool_critique",
                [mock_client],
            ),
            patch(
                "engines.book_content.services.llm_service.sentry_sdk.capture_message"
            ),
        ):
            import engines.book_content.services.llm_service as llm_mod

            llm_mod._current_key_idx = 0
            result = llm_mod.llm_call("Test prompt")

        assert result == ""

    @patch("engines.book_content.services.llm_service.time.sleep", return_value=None)
    def test_llm_call_writer_mode_uses_writer_pool_not_standard(
        self, _mock_sleep: MagicMock
    ) -> None:
        """llm_call(mode='writer') invokes _pool_writer; _pool_standard is untouched."""
        mock_response = MagicMock()
        mock_response.content = "Long article text"
        mock_writer = MagicMock()
        mock_writer.invoke.return_value = mock_response
        mock_standard = MagicMock()

        with (
            patch(
                "engines.book_content.services.llm_service._pool_writer", [mock_writer]
            ),
            patch(
                "engines.book_content.services.llm_service._pool_standard",
                [mock_standard],
            ),
        ):
            from engines.book_content.services.llm_service import llm_call

            llm_call("prompt", mode="writer")

        mock_writer.invoke.assert_called_once()
        mock_standard.invoke.assert_not_called()

    @patch("engines.book_content.services.llm_service.time.sleep", return_value=None)
    def test_llm_call_critique_mode_uses_critique_pool(
        self, _mock_sleep: MagicMock
    ) -> None:
        """llm_call(mode='critique') invokes _pool_critique; others untouched."""
        mock_response = MagicMock()
        mock_response.content = '{"score": 80}'
        mock_critique = MagicMock()
        mock_critique.invoke.return_value = mock_response
        mock_standard = MagicMock()
        mock_writer = MagicMock()

        with (
            patch(
                "engines.book_content.services.llm_service._pool_critique",
                [mock_critique],
            ),
            patch(
                "engines.book_content.services.llm_service._pool_standard",
                [mock_standard],
            ),
            patch(
                "engines.book_content.services.llm_service._pool_writer", [mock_writer]
            ),
        ):
            from engines.book_content.services.llm_service import llm_call

            llm_call("prompt", mode="critique")

        mock_critique.invoke.assert_called_once()
        mock_standard.invoke.assert_not_called()
        mock_writer.invoke.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# WIKI SERVICE
# ─────────────────────────────────────────────────────────────────────────────


class TestWikiService(unittest.TestCase):
    """Tests for engines.book_content.services.wiki_service"""

    @patch("engines.book_content.services.wiki_service.wikipedia.page")
    def test_fetch_full_page_returns_dict_with_all_keys(
        self, mock_page: MagicMock
    ) -> None:
        """fetch_full_page() returns dict with title, content, summary, url, found=True."""
        mock_page.return_value = MagicMock(
            title="Fundamental Rights",
            content="Full article text spanning thousands of words",
            summary="Brief intro summary",
            url="https://en.wikipedia.org/wiki/Fundamental_Rights",
        )

        from engines.book_content.services.wiki_service import fetch_full_page

        result = fetch_full_page("Fundamental Rights")

        assert result["found"] is True
        assert result["title"] == "Fundamental Rights"
        assert result["content"] == "Full article text spanning thousands of words"
        assert result["summary"] == "Brief intro summary"
        assert result["url"] == "https://en.wikipedia.org/wiki/Fundamental_Rights"

    @patch("engines.book_content.services.wiki_service.wikipedia.page")
    def test_fetch_full_page_returns_found_false_on_page_error(
        self, mock_page: MagicMock
    ) -> None:
        """fetch_full_page() returns found=False with empty content when page not found."""
        import wikipedia as wiki_lib

        mock_page.side_effect = wiki_lib.exceptions.PageError("NonExistentPage")

        from engines.book_content.services.wiki_service import fetch_full_page

        result = fetch_full_page("NonExistentPageXYZ999")

        assert result["found"] is False
        assert result["content"] == ""
        assert result["title"] == "NonExistentPageXYZ999"

    @patch("engines.book_content.services.wiki_service.wikipedia.page")
    def test_fetch_full_page_resolves_disambiguation(
        self, mock_page: MagicMock
    ) -> None:
        """fetch_full_page() resolves DisambiguationError by picking the first clean option."""
        import wikipedia as wiki_lib

        # First call raises DisambiguationError; second call (resolved) succeeds
        disambiguation_error = wiki_lib.exceptions.DisambiguationError(
            "Emergency", ["Emergency provisions India", "Emergency (medical)"]
        )
        resolved_page = MagicMock(
            title="Emergency provisions India",
            content="Emergency content",
            summary="Emergency summary",
            url="https://en.wikipedia.org/wiki/Emergency_provisions_India",
        )
        mock_page.side_effect = [disambiguation_error, resolved_page]

        from engines.book_content.services.wiki_service import fetch_full_page

        result = fetch_full_page("Emergency")

        assert result["found"] is True
        assert result["title"] == "Emergency provisions India"

    def test_extract_relevant_section_returns_string_within_max_chars(self) -> None:
        """extract_relevant_section returns str of length ≤ max_chars."""
        from engines.book_content.services.wiki_service import extract_relevant_section

        content = (
            "== Fundamental Rights ==\n"
            "The Fundamental Rights are basic rights. "
            * 50
            + "\n\n== Directive Principles ==\n"
            "DPSP are non-justiciable guidelines. " * 50
        )
        result = extract_relevant_section(content, "Fundamental Rights", max_chars=500)

        assert isinstance(result, str)
        assert len(result) <= 500

    def test_extract_relevant_section_contains_relevant_content(self) -> None:
        """extract_relevant_section prioritises sections matching the subtopic keyword."""
        from engines.book_content.services.wiki_service import extract_relevant_section

        content = (
            "== Article 14 ==\n"
            "Article 14 guarantees equality before law. "
            * 20
            + "\n\n== Article 21 ==\n"
            "Article 21 protects life and liberty. " * 20
        )
        result = extract_relevant_section(content, "Article 14", max_chars=1000)

        assert "Article 14" in result


# ─────────────────────────────────────────────────────────────────────────────
# BOOK PLANNER SERVICE
# ─────────────────────────────────────────────────────────────────────────────


class TestBookPlannerService(unittest.TestCase):
    """Tests for engines.book_content.services.book_planner_service"""

    @patch("engines.book_content.services.book_planner_service.llm_call")
    @patch("engines.book_content.services.book_planner_service._save_book_plan")
    def test_generate_book_plan_returns_dict_with_required_keys(
        self, mock_save: MagicMock, mock_llm: MagicMock
    ) -> None:
        """generate_book_plan() returns dict with toc, reading_order, concept_registry."""
        toc_data = [
            {
                "module": "Constitutional Framework",
                "order": 1,
                "topics": [
                    {
                        "name": "Preamble",
                        "order": 1,
                        "subtopics": ["Meaning", "Significance"],
                        "prerequisites": [],
                    }
                ],
            }
        ]
        prereq_data: dict[str, list[str]] = {"Preamble": []}

        # First call = TOC generation (writer mode), second = prereq (standard mode)
        mock_llm.side_effect = [json.dumps(toc_data), json.dumps(prereq_data)]

        from engines.book_content.services.book_planner_service import (
            generate_book_plan,
        )

        result = generate_book_plan("Indian Polity", ["Constitutional Framework"])

        assert "toc" in result
        assert "reading_order" in result
        assert "concept_registry" in result
        assert isinstance(result["toc"], list)
        assert len(result["toc"]) == 1
        assert result["toc"][0]["module"] == "Constitutional Framework"
        mock_save.assert_called_once()

    @patch("engines.book_content.services.book_planner_service.llm_call")
    @patch("engines.book_content.services.book_planner_service._save_book_plan")
    def test_generate_book_plan_handles_invalid_llm_json_gracefully(
        self, mock_save: MagicMock, mock_llm: MagicMock
    ) -> None:
        """generate_book_plan() returns empty toc (not exception) when LLM returns non-JSON."""
        mock_llm.return_value = "This is NOT valid JSON at all!!!"

        from engines.book_content.services.book_planner_service import (
            generate_book_plan,
        )

        result = generate_book_plan("Test Subject", ["Module A"])

        assert "toc" in result
        assert result["toc"] == []  # _parse_json_list returns []
        assert "reading_order" in result
        assert isinstance(result["reading_order"], list)

    @patch("engines.book_content.services.book_planner_service.llm_call")
    @patch("engines.book_content.services.book_planner_service._save_book_plan")
    def test_generate_book_plan_builds_reading_order_from_toc(
        self, mock_save: MagicMock, mock_llm: MagicMock
    ) -> None:
        """generate_book_plan() reading_order is a flat ordered list of topics."""
        toc_data = [
            {
                "module": "M1",
                "order": 1,
                "topics": [
                    {
                        "name": "Topic A",
                        "order": 1,
                        "subtopics": [],
                        "prerequisites": [],
                    },
                    {
                        "name": "Topic B",
                        "order": 2,
                        "subtopics": [],
                        "prerequisites": ["Topic A"],
                    },
                ],
            }
        ]
        mock_llm.side_effect = [json.dumps(toc_data), "{}"]

        from engines.book_content.services.book_planner_service import (
            generate_book_plan,
        )

        result = generate_book_plan("Test Subject", ["M1"])

        reading_order = result["reading_order"]
        assert isinstance(reading_order, list)
        assert len(reading_order) == 2
        assert reading_order[0]["topic"] == "Topic A"
        assert reading_order[1]["topic"] == "Topic B"


# ─────────────────────────────────────────────────────────────────────────────
# QUALITY ENGINE SERVICE
# ─────────────────────────────────────────────────────────────────────────────


class TestQualityEngineService(unittest.TestCase):
    """Tests for engines.book_content.services.quality_engine_service"""

    # Reusable critique JSON fixtures
    _GOOD_CRITIQUE: dict[str, Any] = {
        "total_score": 82,
        "scores": {
            "specificity": 17,
            "depth": 16,
            "upsc_relevance": 17,
            "no_vagueness": 16,
            "accuracy": 16,
        },
        "weak_sections": [],
        "specific_gaps": [],
        "verdict": "High quality article",
    }
    _LOW_CRITIQUE: dict[str, Any] = {
        "total_score": 55,
        "scores": {
            "specificity": 10,
            "depth": 11,
            "upsc_relevance": 12,
            "no_vagueness": 11,
            "accuracy": 11,
        },
        "weak_sections": ["### Definition & Constitutional Basis"],
        "specific_gaps": ["Missing Article numbers"],
        "verdict": "Needs improvement",
    }

    @patch("engines.book_content.services.quality_engine_service.llm_call")
    def test_generate_quality_article_returns_str_float_tuple(
        self, mock_llm: MagicMock
    ) -> None:
        """generate_quality_article() always returns (str, float) regardless of content."""
        section_body = "Detailed constitutional content. Article 14 states... " * 15

        def _smart_response(prompt: str, mode: str = "standard") -> str:
            # Critique calls use mode="standard"; return score JSON
            if mode == "standard":
                return json.dumps(self._GOOD_CRITIQUE)
            # All writer calls (sections + formatting): return section body
            return section_body

        mock_llm.side_effect = _smart_response

        from engines.book_content.services.quality_engine_service import (
            generate_quality_article,
        )

        result = generate_quality_article(
            subtopic="Article 14 — Right to Equality",
            parent_topic="Fundamental Rights",
            ncert_section="NCERT content on equality",
            wiki_content="Wikipedia content on equality",
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        article, score = result
        assert isinstance(article, str)
        assert isinstance(score, float)
        assert len(article) > 0
        assert 0.0 <= score <= 100.0

    @patch("engines.book_content.services.quality_engine_service.llm_call")
    def test_generate_quality_article_score_reflects_critique(
        self, mock_llm: MagicMock
    ) -> None:
        """Quality score returned equals the total_score from the critique pass."""
        section_body = "Content about Article 19 freedoms. " * 20

        def _smart_response(prompt: str, mode: str = "standard") -> str:
            if mode == "standard":
                return json.dumps(self._GOOD_CRITIQUE)
            return section_body

        mock_llm.side_effect = _smart_response

        from engines.book_content.services.quality_engine_service import (
            generate_quality_article,
        )

        _, score = generate_quality_article(
            subtopic="Article 19",
            parent_topic="Fundamental Rights",
            ncert_section="",
            wiki_content="",
        )

        assert score == 82.0

    @patch("engines.book_content.services.quality_engine_service.llm_call")
    def test_generate_quality_article_triggers_refinement_on_low_score(
        self, mock_llm: MagicMock
    ) -> None:
        """When critique score < 65, refinement pass is triggered and re-scored."""
        section_body = "Content about Fundamental Duties Article 51A. " * 20

        call_count = 0

        def _smart_response(prompt: str, mode: str = "standard") -> str:
            nonlocal call_count
            call_count += 1
            if mode == "standard":
                # First critique call → low score; subsequent → high score
                if call_count <= 7:
                    return json.dumps(self._LOW_CRITIQUE)
                return json.dumps(self._GOOD_CRITIQUE)
            return section_body

        mock_llm.side_effect = _smart_response

        from engines.book_content.services.quality_engine_service import (
            generate_quality_article,
        )

        _, final_score = generate_quality_article(
            subtopic="Fundamental Duties",
            parent_topic="Fundamental Rights",
            ncert_section="",
            wiki_content="",
        )

        # After refinement, the second critique (score=82) should be the final score
        assert final_score == 82.0
        # Refinement means more llm_calls: at minimum 6 sections + 2 critiques + 1 refine
        assert mock_llm.call_count >= 9

    @patch("engines.book_content.services.quality_engine_service.llm_call")
    def test_generate_quality_article_uses_subject_profile_when_provided(
        self, mock_llm: MagicMock
    ) -> None:
        """Subject profile is injected into prompts when subject matches SUBJECT_PROFILES."""
        section_body = "Article content here. " * 20
        captured_prompts: list[str] = []

        def _capture(prompt: str, mode: str = "standard") -> str:
            captured_prompts.append(prompt)
            if mode == "standard":
                return json.dumps(self._GOOD_CRITIQUE)
            return section_body

        mock_llm.side_effect = _capture

        from engines.book_content.services.quality_engine_service import (
            generate_quality_article,
        )

        generate_quality_article(
            subtopic="Emergency Provisions",
            parent_topic="Indian Constitution",
            ncert_section="",
            wiki_content="",
            subject="Indian Constitution & Polity",
        )

        # At least one prompt should contain the subject persona text
        assert any("SUBJECT PERSONA" in p for p in captured_prompts)


# ─────────────────────────────────────────────────────────────────────────────
# INGESTOR SERVICE — SMART SKIP
# Uses Django's TestCase (real DB) but mocks all external services.
# ─────────────────────────────────────────────────────────────────────────────


class TestIngestorSmartSkip(TestCase):
    """
    Smart skip: when BookContent already exists for a subtopic,
    generate_quality_article must NOT be called.
    Uses real DB for the BookContent.objects.filter() smart skip check.
    All external services (LLM, Wikipedia, embeddings, cross-links) are mocked.
    """

    def setUp(self) -> None:
        from engines.knowledge.models import Module, Program, Subject, Topic

        self.program = Program.objects.create(
            name="Smart Skip Test Program",
            description="Phase H smart skip test",
        )
        self.subject = Subject.objects.create(
            name="Smart Skip Subject",
            program=self.program,
            description="test",
            is_active=True,
        )
        self.module = Module.objects.create(
            name="Smart Skip Module",
            subject=self.subject,
            description="test",
            is_active=True,
            order_index=0,
        )
        self.topic = Topic.objects.create(
            name="Smart Skip Topic",
            module=self.module,
            subject=self.subject,
            is_active=True,
            topic_type="syllabus",
            order_index=0,
        )
        self.subtopic = Topic.objects.create(
            name="Pre-Existing Subtopic",
            module=self.module,
            subject=self.subject,
            is_active=True,
            topic_type="syllabus",
            order_index=1,
        )

    @patch("engines.book_content.services.ingestor_service.classify_hierarchy")
    @patch("engines.book_content.services.ingestor_service.find_subtopics")
    @patch("engines.book_content.services.ingestor_service.fetch_full_page")
    @patch("engines.book_content.services.ingestor_service._generate_topic_overview")
    @patch("engines.book_content.services.ingestor_service.generate_quality_article")
    @patch("engines.book_content.services.ingestor_service.update_concept_registry")
    @patch(
        "engines.book_content.services.ingestor_service._create_chunks_and_embeddings"
    )
    @patch("engines.book_content.services.ingestor_service._cross_link_to_ca")
    @patch("engines.book_content.services.ingestor_service._cross_link_inter_subject")
    @patch("engines.book_content.services.ingestor_service.run_coherence_pass")
    @patch("engines.book_content.services.ingestor_service._get_or_create_subject")
    @patch("engines.book_content.services.ingestor_service._get_or_create_module")
    @patch("engines.book_content.services.ingestor_service._get_or_create_topic")
    def test_smart_skip_does_not_call_generate_quality_article(
        self,
        mock_get_topic: MagicMock,
        mock_get_module: MagicMock,
        mock_get_subject: MagicMock,
        mock_coherence: MagicMock,
        mock_inter: MagicMock,
        mock_cross: MagicMock,
        mock_chunks: MagicMock,
        mock_registry: MagicMock,
        mock_quality: MagicMock,
        mock_overview: MagicMock,
        mock_wiki: MagicMock,
        mock_subtopics: MagicMock,
        mock_classify: MagicMock,
    ) -> None:
        """
        Core assertion: BookContent already exists for 'Pre-Existing Subtopic'
        → ingest_topic() must NOT call generate_quality_article for it.
        """
        from engines.book_content.models import BookContent

        # Create pre-existing BookContent for the subtopic
        BookContent.objects.create(
            topic=self.subtopic,
            subject=self.subject,
            content_markdown="Pre-existing article about this subtopic.",
        )

        # Wire hierarchy resolution to our real DB objects
        mock_get_subject.return_value = self.subject
        mock_get_module.return_value = self.module
        mock_get_topic.return_value = self.topic

        mock_classify.return_value = {
            "subject": "Smart Skip Subject",
            "module": "Smart Skip Module",
            "confirmed_topic": "Smart Skip Topic",
        }
        mock_subtopics.return_value = [
            {"name": "Pre-Existing Subtopic", "needs_deep": False}
        ]
        mock_wiki.return_value = {
            "title": "Smart Skip Topic",
            "content": "some content",
            "summary": "brief summary",
            "url": "http://example.com",
            "found": True,
        }
        mock_overview.return_value = "Topic overview text for the main node."

        from engines.book_content.services.ingestor_service import ingest_topic

        ingest_topic(
            topic_name="Smart Skip Topic",
            subject_name="Smart Skip Subject",
        )

        # ── CORE ASSERTION ───────────────────────────────────────────────────
        # Because BookContent existed for 'Pre-Existing Subtopic', smart skip fired
        # and generate_quality_article must NEVER have been called.
        mock_quality.assert_not_called()

        # Concept registry update MUST still run (synced skipping behaviour)
        mock_registry.assert_called()

    @patch("engines.book_content.services.ingestor_service.classify_hierarchy")
    @patch("engines.book_content.services.ingestor_service.find_subtopics")
    @patch("engines.book_content.services.ingestor_service.fetch_full_page")
    @patch("engines.book_content.services.ingestor_service._generate_topic_overview")
    @patch("engines.book_content.services.ingestor_service.generate_quality_article")
    @patch("engines.book_content.services.ingestor_service.update_concept_registry")
    @patch(
        "engines.book_content.services.ingestor_service._create_chunks_and_embeddings"
    )
    @patch("engines.book_content.services.ingestor_service._cross_link_to_ca")
    @patch("engines.book_content.services.ingestor_service._cross_link_inter_subject")
    @patch("engines.book_content.services.ingestor_service.run_coherence_pass")
    @patch("engines.book_content.services.ingestor_service._get_or_create_subject")
    @patch("engines.book_content.services.ingestor_service._get_or_create_module")
    @patch("engines.book_content.services.ingestor_service._get_or_create_topic")
    def test_new_subtopic_does_call_generate_quality_article(
        self,
        mock_get_topic: MagicMock,
        mock_get_module: MagicMock,
        mock_get_subject: MagicMock,
        mock_coherence: MagicMock,
        mock_inter: MagicMock,
        mock_cross: MagicMock,
        mock_chunks: MagicMock,
        mock_registry: MagicMock,
        mock_quality: MagicMock,
        mock_overview: MagicMock,
        mock_wiki: MagicMock,
        mock_subtopics: MagicMock,
        mock_classify: MagicMock,
    ) -> None:
        """
        Inverse test: no pre-existing BookContent → generate_quality_article IS called.
        """
        from engines.knowledge.models import Topic as TopicModel

        # Create a brand new subtopic with NO pre-existing BookContent
        new_subtopic = TopicModel.objects.create(
            name="Brand New Subtopic",
            module=self.module,
            subject=self.subject,
            is_active=True,
            topic_type="syllabus",
            order_index=99,
        )

        mock_get_subject.return_value = self.subject
        mock_get_module.return_value = self.module
        # get_topic called twice: once for main topic, once for new subtopic
        mock_get_topic.side_effect = [self.topic, new_subtopic]

        mock_classify.return_value = {
            "subject": "Smart Skip Subject",
            "module": "Smart Skip Module",
            "confirmed_topic": "Smart Skip Topic",
        }
        mock_subtopics.return_value = [
            {"name": "Brand New Subtopic", "needs_deep": False}
        ]
        mock_wiki.return_value = {
            "title": "T",
            "content": "content",
            "summary": "s",
            "url": "u",
            "found": True,
        }
        mock_overview.return_value = "Overview text"
        mock_quality.return_value = ("Generated article markdown", 78.0)

        from engines.book_content.services.ingestor_service import ingest_topic

        ingest_topic(topic_name="Smart Skip Topic")

        # BookContent did NOT exist → quality article WAS generated
        mock_quality.assert_called_once()
