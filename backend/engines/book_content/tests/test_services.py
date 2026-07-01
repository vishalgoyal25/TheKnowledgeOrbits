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
  - classifier_service: map-hit path, LLM fallback, JSON parsing, prompt content
  - cross_subject_map: lookup_topic, fuzzy_lookup, get_secondary_subjects, SUBJECTS
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

    def _make_pool_entry(self, content: str) -> MagicMock:
        """Build a mock _LLMEntry whose client returns the given content string."""
        mock_message = MagicMock()
        mock_message.content = content
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        entry = MagicMock()
        entry.client = mock_client
        entry.model = "openai/gpt-oss-120b"
        entry.provider = "groq"
        return entry

    def _make_failing_pool_entry(self, exc: Exception) -> MagicMock:
        """Build a mock _LLMEntry whose client always raises exc."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = exc
        entry = MagicMock()
        entry.client = mock_client
        entry.model = "openai/gpt-oss-120b"
        entry.provider = "groq"
        return entry

    @patch("engines.book_content.services.llm_service.time.sleep", return_value=None)
    def test_llm_call_returns_stripped_string_on_success(
        self, _mock_sleep: MagicMock
    ) -> None:
        """llm_call() returns stripped content string from the provider response."""
        entry = self._make_pool_entry("  Article content here.  ")

        with (
            patch("engines.book_content.services.llm_service._pool", [entry]),
            patch("engines.book_content.services.llm_service._pool_size", 1),
        ):
            import engines.book_content.services.llm_service as llm_mod

            llm_mod._current_key_idx = 0
            result = llm_mod.llm_call("Test prompt", mode="standard")

        assert isinstance(result, str)
        assert result == "Article content here."
        entry.client.chat.completions.create.assert_called_once()

    @patch("engines.book_content.services.llm_service.time.sleep", return_value=None)
    def test_llm_call_returns_empty_string_after_all_retries_exhausted(
        self, _mock_sleep: MagicMock
    ) -> None:
        """llm_call() returns '' when every key and every retry fails."""
        entry = self._make_failing_pool_entry(Exception("Rate limit exceeded"))

        with (
            patch("engines.book_content.services.llm_service._pool", [entry]),
            patch("engines.book_content.services.llm_service._pool_size", 1),
            patch(
                "engines.book_content.services.llm_service.sentry_sdk.capture_message"
            ),
        ):
            import engines.book_content.services.llm_service as llm_mod

            llm_mod._current_key_idx = 0
            result = llm_mod.llm_call("Test prompt")

        assert result == ""

    @patch("engines.book_content.services.llm_service.time.sleep", return_value=None)
    def test_llm_call_writer_mode_passes_writer_temperature(
        self, _mock_sleep: MagicMock
    ) -> None:
        """llm_call(mode='writer') uses temperature=0.25 (writer config), not 0.10."""
        entry = self._make_pool_entry("Long article text")

        with (
            patch("engines.book_content.services.llm_service._pool", [entry]),
            patch("engines.book_content.services.llm_service._pool_size", 1),
        ):
            import engines.book_content.services.llm_service as llm_mod

            llm_mod._current_key_idx = 0
            llm_mod.llm_call("prompt", mode="writer")

        call_kwargs = entry.client.chat.completions.create.call_args
        assert call_kwargs.kwargs["temperature"] == 0.25

    @patch("engines.book_content.services.llm_service.time.sleep", return_value=None)
    def test_llm_call_critique_mode_passes_critique_temperature(
        self, _mock_sleep: MagicMock
    ) -> None:
        """llm_call(mode='critique') uses temperature=0.10 (critique config)."""
        entry = self._make_pool_entry('{"score": 80}')

        with (
            patch("engines.book_content.services.llm_service._pool", [entry]),
            patch("engines.book_content.services.llm_service._pool_size", 1),
        ):
            import engines.book_content.services.llm_service as llm_mod

            llm_mod._current_key_idx = 0
            llm_mod.llm_call("prompt", mode="critique")

        call_kwargs = entry.client.chat.completions.create.call_args
        assert call_kwargs.kwargs["temperature"] == 0.10


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
            subject="Indian Polity & Constitution",
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
            node_type="subtopic",  # Phase C smart-skip filter requires this
            parent_topic=self.topic,  # required for seeded DB lookup in Step 4
            order_index=1,
        )

    @patch("engines.book_content.services.ingestor_service.classify_hierarchy")
    @patch("engines.book_content.services.ingestor_service.find_sub_subtopics")
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
    @patch("engines.book_content.services.ingestor_service._get_subject_strict")
    @patch("engines.book_content.services.ingestor_service._get_module_strict")
    @patch("engines.book_content.services.ingestor_service._get_or_match_topic_fuzzy")
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
        mock_sub_subtopics: MagicMock,
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
        # Subtopics now come from seeded DB (Step 4) — no mock needed.
        # find_sub_subtopics (Step 8) is still mocked to avoid LLM calls.
        mock_sub_subtopics.return_value = []
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
    @patch("engines.book_content.services.ingestor_service.find_sub_subtopics")
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
    @patch("engines.book_content.services.ingestor_service._get_subject_strict")
    @patch("engines.book_content.services.ingestor_service._get_module_strict")
    @patch("engines.book_content.services.ingestor_service._get_or_match_topic_fuzzy")
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
        mock_sub_subtopics: MagicMock,
        mock_classify: MagicMock,
    ) -> None:
        """
        Inverse test: no pre-existing BookContent → generate_quality_article IS called.
        """
        from engines.knowledge.models import Topic as TopicModel

        # Create a brand new subtopic with NO pre-existing BookContent.
        # parent_topic=self.topic required so the seeded DB lookup in Step 4 finds it.
        new_subtopic = TopicModel.objects.create(
            name="Brand New Subtopic",
            module=self.module,
            subject=self.subject,
            is_active=True,
            topic_type="syllabus",
            node_type="subtopic",
            parent_topic=self.topic,
            order_index=99,
        )

        mock_get_subject.return_value = self.subject
        mock_get_module.return_value = self.module
        # _get_or_match_topic_fuzzy called 3 times: main topic + new subtopic + pre-existing
        # subtopic (setUp creates both under self.topic, so DB returns 2 subtopics).
        mock_get_topic.side_effect = [self.topic, new_subtopic, self.subtopic]

        mock_classify.return_value = {
            "subject": "Smart Skip Subject",
            "module": "Smart Skip Module",
            "confirmed_topic": "Smart Skip Topic",
        }
        # Subtopics now come from seeded DB (Step 4) — no mock needed.
        # find_sub_subtopics (Step 8) is still mocked to avoid LLM calls.
        mock_sub_subtopics.return_value = []
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

        # BookContent did NOT exist → quality article WAS generated (at least once)
        mock_quality.assert_called()


# ─────────────────────────────────────────────────────────────────────────────
# HIERARCHY ENFORCEMENT — _word_overlap, strict matchers, SkipGenerationError
# ─────────────────────────────────────────────────────────────────────────────


class TestWordOverlap(unittest.TestCase):
    """Tests for engines.book_content.services.ingestor_service._word_overlap"""

    def _fn(self, a: str, b: str) -> float:
        from engines.book_content.services.ingestor_service import _word_overlap

        return _word_overlap(a, b)

    def test_identical_strings_score_one(self) -> None:
        assert self._fn("Union Legislature", "Union Legislature") == 1.0

    def test_exact_word_match_scores_high(self) -> None:
        assert self._fn("Fundamental Rights", "Fundamental Rights") == 1.0

    def test_prefix_stem_match_judicial_judiciary(self) -> None:
        """'Judicial' should match 'Judiciary' via 4-char prefix (judi)."""
        score = self._fn("Judicial System", "Union Judiciary")
        assert score >= 0.25, f"Expected ≥0.25, got {score}"

    def test_prefix_stem_match_legislat(self) -> None:
        """'Legislative' should match 'Legislature' via prefix (legi)."""
        score = self._fn("Legislative Body", "Union Legislature")
        assert score >= 0.25, f"Expected ≥0.25, got {score}"

    def test_completely_unrelated_scores_zero(self) -> None:
        score = self._fn("Cricket Stadium", "Monetary Policy")
        assert score == 0.0

    def test_empty_string_returns_zero(self) -> None:
        assert self._fn("", "Fundamental Rights") == 0.0
        assert self._fn("Fundamental Rights", "") == 0.0

    def test_stopwords_excluded(self) -> None:
        """Stopwords ('of', 'the', 'and') must not contribute to score."""
        # Only stopwords — both stripped to empty → 0.0
        score = self._fn("of the and", "in to a an")
        assert score == 0.0


class TestHierarchyStrictMatchers(TestCase):
    """DB-backed tests for _get_subject_strict and _get_module_strict."""

    def setUp(self) -> None:
        from engines.knowledge.models import Module, Program, Subject

        self.program = Program.objects.create(
            name="Hierarchy Test Program", description="test"
        )
        self.subject = Subject.objects.create(
            name="Indian Polity & Constitution",
            program=self.program,
            description="test",
            is_active=True,
        )
        self.module = Module.objects.create(
            name="Union Legislature",
            subject=self.subject,
            description="test",
            is_active=True,
            order_index=1,
        )

    def test_get_subject_strict_exact_match(self) -> None:
        from engines.book_content.services.ingestor_service import _get_subject_strict

        result = _get_subject_strict("Indian Polity & Constitution")
        assert result is not None
        assert result.name == "Indian Polity & Constitution"

    def test_get_subject_strict_case_insensitive(self) -> None:
        from engines.book_content.services.ingestor_service import _get_subject_strict

        result = _get_subject_strict("indian polity & constitution")
        assert result is not None

    def test_get_subject_strict_no_match_returns_none(self) -> None:
        from engines.book_content.services.ingestor_service import _get_subject_strict

        result = _get_subject_strict("Completely Invented Subject XYZ999")
        assert result is None

    def test_get_module_strict_exact_match(self) -> None:
        from engines.book_content.services.ingestor_service import _get_module_strict

        result = _get_module_strict("Union Legislature", self.subject)
        assert result is not None
        assert result.name == "Union Legislature"

    def test_get_module_strict_no_match_returns_none(self) -> None:
        from engines.book_content.services.ingestor_service import _get_module_strict

        result = _get_module_strict("Completely Invented Module XYZ999", self.subject)
        assert result is None


class TestSkipGenerationError(TestCase):
    """ingest_topic() returns a skip dict — never raises — when hierarchy not found."""

    def setUp(self) -> None:
        from engines.knowledge.models import Program, Subject

        self.program = Program.objects.create(
            name="Skip Error Test Program", description="test"
        )
        Subject.objects.create(
            name="Known Subject",
            program=self.program,
            description="test",
            is_active=True,
        )

    @patch("engines.book_content.services.ingestor_service.classify_hierarchy")
    def test_unknown_subject_returns_skip_dict(self, mock_classify: MagicMock) -> None:
        """When LLM returns a subject not in DB, ingest_topic returns skip dict."""
        mock_classify.return_value = {
            "subject": "Completely Invented Subject That Does Not Exist",
            "module": "Some Module",
            "confirmed_topic": "Some Topic",
        }

        from engines.book_content.services.ingestor_service import ingest_topic

        result = ingest_topic(topic_name="Some Topic")

        assert result.get("skipped") is True
        assert "reason" in result
        assert result["nodes_created"] == 0

    @patch("engines.book_content.services.ingestor_service.classify_hierarchy")
    @patch("engines.book_content.services.ingestor_service._get_subject_strict")
    def test_unknown_module_returns_skip_dict(
        self,
        mock_subject: MagicMock,
        mock_classify: MagicMock,
    ) -> None:
        """When subject matches but module is invented, ingest_topic returns skip dict."""
        from engines.knowledge.models import Subject

        subj = Subject.objects.get(name="Known Subject")
        # No modules seeded → _get_module_strict will return None
        mock_subject.return_value = subj
        mock_classify.return_value = {
            "subject": "Known Subject",
            "module": "Invented Module That Does Not Exist",
            "confirmed_topic": "Some Topic",
        }

        from engines.book_content.services.ingestor_service import ingest_topic

        result = ingest_topic(topic_name="Some Topic")

        assert result.get("skipped") is True
        assert result["nodes_created"] == 0


class TestTopicLocking(TestCase):
    """_find_complete_topic returns None unless content_status='complete'."""

    def setUp(self) -> None:
        from engines.knowledge.models import Module, Program, Subject, Topic

        self.program = Program.objects.create(
            name="Locking Test Program", description="test"
        )
        self.subject = Subject.objects.create(
            name="Locking Subject",
            program=self.program,
            description="test",
            is_active=True,
        )
        self.module = Module.objects.create(
            name="Locking Module",
            subject=self.subject,
            description="test",
            is_active=True,
            order_index=1,
        )
        self.topic_incomplete = Topic.objects.create(
            name="River Systems of India",
            module=self.module,
            subject=self.subject,
            is_active=True,
            topic_type="syllabus",
            order_index=1,
            content_status="book_quality",
        )
        self.topic_complete = Topic.objects.create(
            name="Fully Complete Topic",
            module=self.module,
            subject=self.subject,
            is_active=True,
            topic_type="syllabus",
            order_index=2,
            content_status="complete",
        )

    def test_find_complete_topic_returns_none_for_incomplete(self) -> None:
        from engines.book_content.services.ingestor_service import _find_complete_topic

        result = _find_complete_topic("River Systems of India")
        assert result is None

    def test_find_complete_topic_returns_topic_when_complete(self) -> None:
        from engines.book_content.services.ingestor_service import _find_complete_topic

        result = _find_complete_topic("Fully Complete Topic")
        assert result is not None
        assert result.name == "Fully Complete Topic"

    def test_find_complete_topic_returns_none_for_unknown(self) -> None:
        from engines.book_content.services.ingestor_service import _find_complete_topic

        result = _find_complete_topic("Topic That Does Not Exist XYZ")
        assert result is None

    @patch("engines.book_content.services.ingestor_service._extend_sub_subtopics_only")
    def test_ingest_topic_routes_to_extend_when_locked(
        self, mock_extend: MagicMock
    ) -> None:
        """Locked topic (content_status='complete') routes to _extend_sub_subtopics_only."""
        mock_extend.return_value = {
            "nodes_created": 0,
            "relations_created": 0,
            "topic": "Fully Complete Topic",
            "locked_extension": True,
        }

        from engines.book_content.services.ingestor_service import ingest_topic

        result = ingest_topic(topic_name="Fully Complete Topic")

        mock_extend.assert_called_once()
        assert result.get("locked_extension") is True


# ─────────────────────────────────────────────────────────────────────────────
# CLASSIFIER SERVICE
# ─────────────────────────────────────────────────────────────────────────────


class TestClassifierService(unittest.TestCase):
    """
    Tests for engines.book_content.services.classifier_service.

    No real LLM calls; no DB required for most tests.
    _load_seeded_hierarchy() is patched where DB access would be needed.
    """

    # ── _parse_json ──────────────────────────────────────────────────────────

    def test_parse_json_valid_string(self) -> None:
        """Valid JSON string is parsed and returned as dict."""
        from engines.book_content.services.classifier_service import _parse_json

        raw = '{"subject":"Indian Polity & Constitution","module":"Union Legislature","confirmed_topic":"Parliament","secondary_subjects":[]}'
        result = _parse_json(raw)
        assert result["subject"] == "Indian Polity & Constitution"
        assert result["module"] == "Union Legislature"
        assert result["confirmed_topic"] == "Parliament"
        assert result["secondary_subjects"] == []

    def test_parse_json_wrapped_in_markdown_fences(self) -> None:
        """JSON wrapped inside a larger text string is still extracted correctly."""
        from engines.book_content.services.classifier_service import _parse_json

        raw = 'Here is the result:\n{"subject":"Indian Economy & Agriculture","module":"Fiscal Policy","confirmed_topic":"Budget","secondary_subjects":["Governance & Social Justice"]}\nDone.'
        result = _parse_json(raw)
        assert result["subject"] == "Indian Economy & Agriculture"
        assert result["module"] == "Fiscal Policy"

    def test_parse_json_invalid_returns_safe_defaults(self) -> None:
        """Completely broken JSON returns safe default dict without raising."""
        from engines.book_content.services.classifier_service import _parse_json

        result = _parse_json("This is not JSON at all!!!")
        assert result["subject"] == "Indian Polity & Constitution"
        assert result["module"] == "General Topics"
        assert result["confirmed_topic"] == ""
        assert result["secondary_subjects"] == []

    def test_parse_json_empty_string_returns_safe_defaults(self) -> None:
        """Empty string returns safe defaults."""
        from engines.book_content.services.classifier_service import _parse_json

        result = _parse_json("")
        assert isinstance(result, dict)
        assert "subject" in result

    # ── _build_topic_prompt ──────────────────────────────────────────────────

    def test_build_topic_prompt_contains_critical_rules(self) -> None:
        """_build_topic_prompt must include 'CRITICAL RULES' block to prevent LLM hallucination."""
        _FAKE_HIERARCHY = "EXACT subject and module names seeded in the database:\n\nSubject: Indian Polity & Constitution\n  - Union Legislature"

        with patch(
            "engines.book_content.services.classifier_service._load_seeded_hierarchy",
            return_value=_FAKE_HIERARCHY,
        ):
            from engines.book_content.services.classifier_service import (
                _build_topic_prompt,
            )

            prompt = _build_topic_prompt("Parliament of India")

        assert "CRITICAL RULES" in prompt
        assert "character-for-character" in prompt

    def test_build_topic_prompt_contains_hierarchy_text(self) -> None:
        """_build_topic_prompt embeds the hierarchy string returned by _load_seeded_hierarchy."""
        _FAKE_HIERARCHY = "Subject: TestSubject\n  - TestModule"

        with patch(
            "engines.book_content.services.classifier_service._load_seeded_hierarchy",
            return_value=_FAKE_HIERARCHY,
        ):
            from engines.book_content.services.classifier_service import (
                _build_topic_prompt,
            )

            prompt = _build_topic_prompt("Any Topic")

        assert "TestSubject" in prompt
        assert "TestModule" in prompt

    def test_build_topic_prompt_includes_topic_name(self) -> None:
        """The supplied topic_name appears verbatim in the generated prompt."""
        with patch(
            "engines.book_content.services.classifier_service._load_seeded_hierarchy",
            return_value="Subjects: ...",
        ):
            from engines.book_content.services.classifier_service import (
                _build_topic_prompt,
            )

            prompt = _build_topic_prompt("Fundamental Rights")

        assert "Fundamental Rights" in prompt

    # ── classify_hierarchy — map-hit path ────────────────────────────────────

    def test_classify_hierarchy_map_hit_skips_llm(self) -> None:
        """When fuzzy_lookup finds the topic, llm_call must NOT be called."""
        _MAP_ENTRY = {
            "primary_subject": "Indian Polity & Constitution",
            "module": "Union Legislature",
            "secondary_subjects": ["Governance & Social Justice"],
        }
        with (
            patch(
                "engines.book_content.services.classifier_service.fuzzy_lookup",
                return_value=_MAP_ENTRY,
            ),
            patch(
                "engines.book_content.services.classifier_service.llm_call"
            ) as mock_llm,
        ):
            from engines.book_content.services.classifier_service import (
                classify_hierarchy,
            )

            result = classify_hierarchy(topic_name="Parliament of India")

        mock_llm.assert_not_called()
        assert result["subject"] == "Indian Polity & Constitution"
        assert result["module"] == "Union Legislature"
        assert result["confirmed_topic"] == "Parliament of India"
        assert "Governance & Social Justice" in result["secondary_subjects"]

    # ── classify_hierarchy — LLM fallback path ──────────────────────────────

    def test_classify_hierarchy_llm_fallback_called_for_unknown_topic(self) -> None:
        """When fuzzy_lookup returns None, llm_call is invoked for classification."""
        _LLM_JSON = json.dumps(
            {
                "subject": "Indian Polity & Constitution",
                "module": "Constitutional Framework",
                "confirmed_topic": "Unknown Topic XYZ",
                "secondary_subjects": [],
            }
        )
        with (
            patch(
                "engines.book_content.services.classifier_service.fuzzy_lookup",
                return_value=None,
            ),
            patch(
                "engines.book_content.services.classifier_service.llm_call",
                return_value=_LLM_JSON,
            ) as mock_llm,
            patch(
                "engines.book_content.services.classifier_service._load_seeded_hierarchy",
                return_value="Subject: Indian Polity & Constitution\n  - Constitutional Framework",
            ),
        ):
            from engines.book_content.services.classifier_service import (
                classify_hierarchy,
            )

            result = classify_hierarchy(topic_name="Unknown Topic XYZ")

        mock_llm.assert_called_once()
        assert result["subject"] == "Indian Polity & Constitution"

    def test_classify_hierarchy_unknown_subject_kept_not_forced_to_polity(
        self,
    ) -> None:
        """
        Phase 6 contract: an unrecognised LLM subject is KEPT as-is — NOT silently
        coerced to 'Indian Polity & Constitution'. The downstream strict resolver
        (_get_subject_strict) fuzzy-matches against seeded subjects or raises a
        clean skip. The old blind Polity default was the root cause that mis-routed
        whole subjects (Ethics/Geography/Economy) into empty-complete topics.
        """
        _LLM_JSON = json.dumps(
            {
                "subject": "Totally Made Up Subject",
                "module": "Some Module",
                "confirmed_topic": "Test Topic",
                "secondary_subjects": [],
            }
        )
        with (
            patch(
                "engines.book_content.services.classifier_service.fuzzy_lookup",
                return_value=None,
            ),
            patch(
                "engines.book_content.services.classifier_service.llm_call",
                return_value=_LLM_JSON,
            ),
            patch(
                "engines.book_content.services.classifier_service._load_seeded_hierarchy",
                return_value="Subjects: ...",
            ),
            patch(
                "engines.book_content.services.classifier_service._seeded_subject_names",
                return_value=[
                    "Indian Polity & Constitution",
                    "Ethics, Integrity & Aptitude",
                    "Indian & World Geography",
                ],
            ),
        ):
            from engines.book_content.services.classifier_service import (
                classify_hierarchy,
            )

            result = classify_hierarchy(topic_name="Test Topic")

        # New contract: an unknown subject is NOT force-defaulted to Polity;
        # it is kept verbatim for the strict resolver to handle.
        assert result["subject"] != "Indian Polity & Constitution"
        assert result["subject"] == "Totally Made Up Subject"

    def test_classify_hierarchy_preserves_valid_seeded_subject(self) -> None:
        """
        Regression guard for the keystone bug: a correctly classified subject that
        IS seeded (e.g. 'Ethics, Integrity & Aptitude') must be preserved exactly —
        never rewritten to 'Indian Polity & Constitution'. Before Phase 6 the stale
        whitelist rejected this real subject and force-defaulted it to Polity.
        """
        _LLM_JSON = json.dumps(
            {
                "subject": "Ethics, Integrity & Aptitude",
                "module": "Ethics and Human Values",
                "confirmed_topic": "Essence and Dimensions of Ethics",
                "secondary_subjects": [],
            }
        )
        with (
            patch(
                "engines.book_content.services.classifier_service.fuzzy_lookup",
                return_value=None,
            ),
            patch(
                "engines.book_content.services.classifier_service.llm_call",
                return_value=_LLM_JSON,
            ),
            patch(
                "engines.book_content.services.classifier_service._load_seeded_hierarchy",
                return_value="Subjects: ...",
            ),
            patch(
                "engines.book_content.services.classifier_service._seeded_subject_names",
                return_value=[
                    "Indian Polity & Constitution",
                    "Ethics, Integrity & Aptitude",
                    "Indian & World Geography",
                ],
            ),
        ):
            from engines.book_content.services.classifier_service import (
                classify_hierarchy,
            )

            result = classify_hierarchy(topic_name="Essence and Dimensions of Ethics")

        assert result["subject"] == "Ethics, Integrity & Aptitude"


# ─────────────────────────────────────────────────────────────────────────────
# CROSS SUBJECT MAP
# ─────────────────────────────────────────────────────────────────────────────


class TestCrossSubjectMap(unittest.TestCase):
    """
    Tests for engines.book_content.services.cross_subject_map.
    Pure in-memory operations — no DB, no HTTP, no mocks needed.
    """

    # ── SUBJECTS dict ────────────────────────────────────────────────────────

    def test_subjects_dict_has_required_keys(self) -> None:
        """SUBJECTS must contain all 9 canonical UPSC subject keys."""
        from engines.book_content.services.cross_subject_map import SUBJECTS

        required_keys = {
            "POLITY",
            "HISTORY",
            "GEOGRAPHY",
            "ECONOMY",
            "ENVIRONMENT",
            "SCIENCE",
            "IR",
            "GOVERNANCE",
            "SECURITY",
        }
        assert required_keys.issubset(set(SUBJECTS.keys()))

    def test_subjects_values_are_non_empty_strings(self) -> None:
        """Every value in SUBJECTS is a non-empty string (canonical name)."""
        from engines.book_content.services.cross_subject_map import SUBJECTS

        for key, value in SUBJECTS.items():
            assert (
                isinstance(value, str) and value.strip()
            ), f"SUBJECTS[{key!r}] must be a non-empty string"

    # ── lookup_topic ─────────────────────────────────────────────────────────

    def test_lookup_topic_returns_entry_for_canonical_name(self) -> None:
        """Exact canonical name returns the correct registry entry."""
        from engines.book_content.services.cross_subject_map import lookup_topic

        entry = lookup_topic("Parliament of India")
        assert entry is not None
        assert entry["module"] == "Union Legislature"

    def test_lookup_topic_returns_none_for_unknown(self) -> None:
        """Unknown topic name returns None."""
        from engines.book_content.services.cross_subject_map import lookup_topic

        assert lookup_topic("Nonexistent Topic XYZABC") is None

    # ── fuzzy_lookup ─────────────────────────────────────────────────────────

    def test_fuzzy_lookup_finds_by_exact_canonical_name(self) -> None:
        """fuzzy_lookup with exact canonical name returns the entry."""
        from engines.book_content.services.cross_subject_map import fuzzy_lookup

        entry = fuzzy_lookup("Climate Change")
        assert entry is not None
        assert "primary_subject" in entry

    def test_fuzzy_lookup_finds_by_alias(self) -> None:
        """fuzzy_lookup with a known alias ('ISRO') resolves to Space Technology entry."""
        from engines.book_content.services.cross_subject_map import fuzzy_lookup

        entry = fuzzy_lookup("ISRO")
        assert entry is not None
        assert entry["module"] == "Space Technology"

    def test_fuzzy_lookup_finds_by_partial_match(self) -> None:
        """'Budget' is a partial match for 'Budget & Fiscal Policy'."""
        from engines.book_content.services.cross_subject_map import fuzzy_lookup

        entry = fuzzy_lookup("Budget")
        assert entry is not None
        assert entry["module"] == "Fiscal Policy"

    def test_fuzzy_lookup_returns_none_for_unrelated_string(self) -> None:
        """A completely unrelated string returns None."""
        from engines.book_content.services.cross_subject_map import fuzzy_lookup

        assert fuzzy_lookup("ZXQWRandomNonsense12345") is None

    def test_fuzzy_lookup_case_insensitive_canonical(self) -> None:
        """Lowercase canonical name still resolves via fuzzy_lookup."""
        from engines.book_content.services.cross_subject_map import fuzzy_lookup

        entry = fuzzy_lookup("parliament of india")
        assert entry is not None

    # ── get_secondary_subjects ────────────────────────────────────────────────

    def test_get_secondary_subjects_returns_list_for_known_topic(self) -> None:
        """Known topic returns its secondary_subjects list (may be empty or non-empty)."""
        from engines.book_content.services.cross_subject_map import (
            get_secondary_subjects,
        )

        result = get_secondary_subjects("Climate Change")
        assert isinstance(result, list)
        # Climate Change spans Geography, Economy, IR — at least one secondary subject
        assert len(result) >= 1

    def test_get_secondary_subjects_returns_empty_list_for_unknown(self) -> None:
        """Unknown topic returns an empty list — never raises."""
        from engines.book_content.services.cross_subject_map import (
            get_secondary_subjects,
        )

        result = get_secondary_subjects("Completely Unknown Topic XYZABC")
        assert result == []

    def test_get_secondary_subjects_ethics_has_none(self) -> None:
        """Ethics, Integrity & Aptitude has secondary_subjects=[] by design."""
        from engines.book_content.services.cross_subject_map import (
            get_secondary_subjects,
        )

        result = get_secondary_subjects("Ethics, Integrity & Aptitude")
        assert result == []
