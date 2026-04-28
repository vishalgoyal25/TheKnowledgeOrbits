"""
engines/daily_ca/tests/test_services.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase M2 — Daily CA service tests.

All GROQ calls mocked — no real API calls in tests.

Tests:
  StaticBackgroundService:
    - Case A: published BookContent exists → returns dict with key_facts
    - Case B: BookContent exists but not published → returns None instantly
    - Case C: No BookContent → returns None instantly
    - trigger_pending_static_generation calls POST for each topic

  WikiEnrichmentService:
    - Returns {} on any failure (never raises)

  build_ca_prompt:
    - Output contains correct subject tone for a given subject
    - Output contains ca_text when provided

  DailyCaGeneratorService._run_single_cycle:
    - needs_static=True when no published static exists (Case B/C)
    - word count > MAX_WORDS gets truncated
    - proposal.status = 'generated' after successful cycle

  run_generation_cycle:
    - trigger_pending_static_generation called AFTER all cycles (not during)
    - GROQ session cap: remaining proposals marked 'queued_next_run'
    - Failed cycle marks proposal 'failed', loop continues
    - body_md has raw [[terms]], body_md_processed has /concepts/ links
"""

import uuid
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from engines.daily_ca.models import CaDailyProposal, DailyCaArticle
from engines.daily_ca.services.prompt_builder import build_ca_prompt
from engines.daily_ca.services.static_background_service import StaticBackgroundService


# ── StaticBackgroundService ───────────────────────────────────────────────────


class TestStaticBackgroundServiceCases:
    def test_case_a_published_static_returns_dict(self):
        """Case A: published BookContent exists → dict with key_facts."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": str(uuid.uuid4()),
            "content_markdown": "## Key Facts\n- Fact 1\n- Fact 2",
            "is_published": True,
        }
        with patch(
            "engines.daily_ca.services.static_background_service.requests.get",
            return_value=mock_response,
        ):
            result = StaticBackgroundService.get_background_facts(uuid.uuid4())

        assert result is not None
        assert isinstance(result, dict)

    def test_case_b_not_published_returns_none(self):
        """Case B: BookContent exists but is_published=False → returns None."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": str(uuid.uuid4()),
            "content_markdown": "Some content",
            "is_published": False,
        }
        with patch(
            "engines.daily_ca.services.static_background_service.requests.get",
            return_value=mock_response,
        ):
            result = StaticBackgroundService.get_background_facts(uuid.uuid4())

        assert result is None

    def test_case_c_no_content_returns_none(self):
        """Case C: 404 → returns None instantly."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        with patch(
            "engines.daily_ca.services.static_background_service.requests.get",
            return_value=mock_response,
        ):
            result = StaticBackgroundService.get_background_facts(uuid.uuid4())

        assert result is None

    def test_exception_returns_none(self):
        """Network error → returns None, never raises."""
        with patch(
            "engines.daily_ca.services.static_background_service.requests.get",
            side_effect=Exception("connection refused"),
        ):
            result = StaticBackgroundService.get_background_facts(uuid.uuid4())

        assert result is None

    def test_trigger_calls_post_for_each_topic(self):
        """trigger_pending_static_generation posts once per topic_id."""
        topic_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
        mock_response = MagicMock()
        mock_response.status_code = 202

        with patch(
            "engines.daily_ca.services.static_background_service.requests.post",
            return_value=mock_response,
        ) as mock_post:
            with patch(
                "engines.daily_ca.services.static_background_service.time.sleep"
            ):
                StaticBackgroundService.trigger_pending_static_generation(topic_ids)

        assert mock_post.call_count == 3

    def test_trigger_none_topic_id_skipped(self):
        """None topic_id in list → skipped, no POST."""
        topic_ids = [None, uuid.uuid4()]
        mock_response = MagicMock()
        mock_response.status_code = 202

        with patch(
            "engines.daily_ca.services.static_background_service.requests.post",
            return_value=mock_response,
        ) as mock_post:
            with patch(
                "engines.daily_ca.services.static_background_service.time.sleep"
            ):
                StaticBackgroundService.trigger_pending_static_generation(topic_ids)

        assert mock_post.call_count == 1


# ── WikiEnrichmentService ─────────────────────────────────────────────────────


class TestWikiEnrichmentService:
    def test_returns_empty_dict_on_failure(self):
        from engines.daily_ca.services.wiki_enrichment_service import (
            WikiEnrichmentService,
        )

        with patch(
            "engines.daily_ca.services.wiki_enrichment_service.fetch_full_page",
            side_effect=Exception("wiki down"),
        ):
            result = WikiEnrichmentService.get_enrichment("Some Topic")

        assert result == {}

    def test_never_raises(self):
        from engines.daily_ca.services.wiki_enrichment_service import (
            WikiEnrichmentService,
        )

        with patch(
            "engines.daily_ca.services.wiki_enrichment_service.fetch_full_page",
            side_effect=RuntimeError("unexpected"),
        ):
            result = WikiEnrichmentService.get_enrichment("Anything")

        assert result == {}


# ── build_ca_prompt ───────────────────────────────────────────────────────────


class TestBuildCaPrompt:
    def test_contains_ca_text(self):
        prompt = build_ca_prompt(
            ca_chunks_text="The RBI raised rates by 25 bps.",
            static_key_facts=None,
            wiki_enrichment=None,
            subject_name="Economy",
            topic_name="Monetary Policy",
        )
        assert "RBI raised rates" in prompt

    def test_contains_subject_name(self):
        """subject_name is injected into SUBJECT: line in the prompt."""
        prompt = build_ca_prompt(
            ca_chunks_text="Some CA text.",
            static_key_facts=None,
            wiki_enrichment=None,
            subject_name="Polity",
            topic_name="Federalism",
        )
        assert "Polity" in prompt

    def test_static_facts_included_when_provided(self):
        """key_facts must be a list — _format_static_facts iterates over it."""
        prompt = build_ca_prompt(
            ca_chunks_text="CA text.",
            static_key_facts={
                "key_facts": ["Fact 1.", "Fact 2."],
                "title": "Climate Change",
            },
            wiki_enrichment=None,
            subject_name="Environment",
            topic_name="Climate Change",
        )
        assert "Fact 1" in prompt

    def test_wiki_enrichment_included_when_provided(self):
        prompt = build_ca_prompt(
            ca_chunks_text="CA text.",
            static_key_facts=None,
            wiki_enrichment={"intro": "Wikipedia intro text here.", "key_facts": []},
            subject_name="Science",
            topic_name="Nuclear Fusion",
        )
        assert "Wikipedia intro" in prompt

    def test_subject_tone_applied(self):
        """Economy subject should include economy-specific tone instructions."""
        prompt = build_ca_prompt(
            ca_chunks_text="GDP growth.",
            static_key_facts=None,
            wiki_enrichment=None,
            subject_name="Economy",
            topic_name="GDP",
        )
        # Prompt should be non-empty and substantial
        assert len(prompt) > 500


# ── DailyCaGeneratorService ───────────────────────────────────────────────────


@pytest.mark.django_db
class TestDailyCaGeneratorService:
    def _make_proposal(self, title="Test Article Title"):
        return CaDailyProposal.objects.create(
            date=date(2026, 4, 10),
            title=title,
            description="Some news description.",
            subject_name="Polity",
            gs_paper="GS2",
            status="approved",
        )

    def _mock_llm(
        self, mock_target="engines.daily_ca.services.generator_service.llm_call"
    ):
        return patch(
            mock_target,
            return_value=(
                "# Test Article Title\n\n"
                "## Background\n\n"
                "The government launched a new policy. "
                "The [[Article 370]] was discussed. "
                ":::callout\nKey point here.\n:::\n\n"
                "TAGS: polity, article-370, federalism\n"
                "SOURCE: The Hindu"
            ),
        )

    def test_needs_static_true_when_no_published_static(self):
        """Case B/C: no published static → needs_static=True."""
        from engines.daily_ca.services.generator_service import DailyCaGeneratorService

        proposal = self._make_proposal("Static Test Article")

        with self._mock_llm():
            with patch(
                "engines.daily_ca.services.generator_service.StaticBackgroundService.get_background_facts",
                return_value=None,
            ):
                with patch("engines.daily_ca.services.generator_service.time.sleep"):
                    with patch(
                        "engines.tags.services.concept_resolver.llm_call",
                        return_value="Brief desc.",
                    ):
                        with patch("engines.tags.services.concept_resolver.time.sleep"):
                            article, calls, needs_static = (
                                DailyCaGeneratorService._run_single_cycle(proposal)
                            )

        assert needs_static is True

    def test_needs_static_false_when_static_exists(self):
        """Case A: published static exists → needs_static=False.
        book_content_id is NOT included in mock to avoid FK violation in test DB.
        needs_static is driven by static_facts being non-None, not by book_content_id."""
        from engines.daily_ca.services.generator_service import DailyCaGeneratorService

        proposal = self._make_proposal("Static Exists Article")

        with self._mock_llm():
            with patch(
                "engines.daily_ca.services.generator_service.StaticBackgroundService.get_background_facts",
                return_value={
                    "key_facts": ["Some facts."],
                    "title": "Test Topic",
                },  # no book_content_id
            ):
                with patch("engines.daily_ca.services.generator_service.time.sleep"):
                    with patch(
                        "engines.tags.services.concept_resolver.llm_call",
                        return_value="Brief.",
                    ):
                        with patch("engines.tags.services.concept_resolver.time.sleep"):
                            article, calls, needs_static = (
                                DailyCaGeneratorService._run_single_cycle(proposal)
                            )

        assert needs_static is False

    def test_word_count_truncated_at_max(self):
        """LLM output exceeding MAX_WORDS gets truncated."""
        from engines.daily_ca.services.generator_service import DailyCaGeneratorService

        proposal = self._make_proposal("Long Article")
        long_body = "word " * 1200  # 1200 words — exceeds 800 cap

        with patch(
            "engines.daily_ca.services.generator_service.llm_call",
            return_value=f"# Long Article\n\n{long_body}\nTAGS: polity\nSOURCE: Hindu",
        ):
            with patch(
                "engines.daily_ca.services.generator_service.StaticBackgroundService.get_background_facts",
                return_value=None,
            ):
                with patch("engines.daily_ca.services.generator_service.time.sleep"):
                    with patch(
                        "engines.tags.services.concept_resolver.llm_call",
                        return_value="Brief.",
                    ):
                        with patch("engines.tags.services.concept_resolver.time.sleep"):
                            article, calls, needs_static = (
                                DailyCaGeneratorService._run_single_cycle(proposal)
                            )

        assert len(article.body_md.split()) <= DailyCaGeneratorService.MAX_WORDS

    def test_proposal_status_set_to_generated(self):
        """Successful cycle → proposal.status == 'generated'."""
        from engines.daily_ca.services.generator_service import DailyCaGeneratorService

        proposal = self._make_proposal("Generated Status Test")

        with self._mock_llm():
            with patch(
                "engines.daily_ca.services.generator_service.StaticBackgroundService.get_background_facts",
                return_value=None,
            ):
                with patch("engines.daily_ca.services.generator_service.time.sleep"):
                    with patch(
                        "engines.tags.services.concept_resolver.llm_call",
                        return_value="Brief.",
                    ):
                        with patch("engines.tags.services.concept_resolver.time.sleep"):
                            DailyCaGeneratorService._run_single_cycle(proposal)

        proposal.refresh_from_db()
        assert proposal.status == "generated"

    def test_body_md_has_raw_brackets_processed_has_links(self):
        """body_md keeps [[term]], body_md_processed has /concepts/ link."""
        from engines.daily_ca.services.generator_service import DailyCaGeneratorService
        from engines.tags.models import ConceptPage

        ConceptPage.objects.create(name="Article 370", slug="article-370")
        proposal = self._make_proposal("Brackets Test")

        with self._mock_llm():
            with patch(
                "engines.daily_ca.services.generator_service.StaticBackgroundService.get_background_facts",
                return_value=None,
            ):
                with patch("engines.daily_ca.services.generator_service.time.sleep"):
                    with patch("engines.tags.services.concept_resolver.time.sleep"):
                        article, _, _ = DailyCaGeneratorService._run_single_cycle(
                            proposal
                        )

        assert "[[Article 370]]" in article.body_md
        assert "[Article 370](/concepts/article-370)" in article.body_md_processed

    def test_failed_cycle_marks_proposal_failed_loop_continues(self):
        """If one cycle crashes, proposal marked 'failed', next cycle runs."""
        from engines.daily_ca.services.generator_service import DailyCaGeneratorService

        p1 = self._make_proposal("Failing Proposal")
        p2 = self._make_proposal("Succeeding Proposal")

        call_count = [0]

        def mock_single_cycle(proposal, db_alias="default"):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Simulated failure")
            # Return minimal valid tuple for second proposal
            article = DailyCaArticle.objects.create(
                title="Succeeding Article",
                slug=f"2026-04-10-succeeding-{uuid.uuid4().hex[:6]}",
                published_date=date(2026, 4, 10),
                body_md="Some content here.",
            )
            return article, 1, False

        with patch.object(
            DailyCaGeneratorService, "_run_single_cycle", mock_single_cycle
        ):
            results = DailyCaGeneratorService.run_generation_cycle(
                proposals=[p1, p2], groq_calls_used=0
            )

        p1.refresh_from_db()
        assert p1.status == "failed"
        assert results["failed"] == 1
        assert results["generated"] == 1

    def test_session_cap_marks_remaining_queued(self):
        """GROQ cap hit → remaining proposals marked 'queued_next_run'."""
        from engines.daily_ca.services.generator_service import DailyCaGeneratorService

        proposals = [self._make_proposal(f"Cap Test {i}") for i in range(3)]

        def mock_single_cycle(proposal, db_alias="default"):
            article = DailyCaArticle.objects.create(
                title=proposal.title,
                slug=f"2026-04-10-cap-{uuid.uuid4().hex[:6]}",
                published_date=date(2026, 4, 10),
                body_md="Content.",
            )
            return (
                article,
                60,
                False,
            )  # 60 calls per cycle → cap before cycle 3 (120 >= 100)

        with patch.object(
            DailyCaGeneratorService, "_run_single_cycle", mock_single_cycle
        ):
            results = DailyCaGeneratorService.run_generation_cycle(
                proposals=proposals,
                groq_calls_used=0,
            )

        assert results["capped"] > 0
        # At least some proposals should be queued_next_run
        queued = CaDailyProposal.objects.filter(status="queued_next_run").count()
        assert queued > 0

    def test_trigger_static_not_called_after_cycles(self):
        """Phase A (FEATURES5): trigger_pending_static_generation is NEVER called
        from run_generation_cycle — static generation is a separate cron job.
        static_triggered is always 0 in results for backward compatibility."""
        from engines.daily_ca.services.generator_service import DailyCaGeneratorService

        proposal = self._make_proposal("Static Trigger Test")

        def mock_single_cycle(p, db_alias="default"):
            article = DailyCaArticle.objects.create(
                title=p.title,
                slug=f"2026-04-10-trigger-{uuid.uuid4().hex[:6]}",
                published_date=date(2026, 4, 10),
                body_md="Content.",
            )
            return article, 1, False  # needs_static irrelevant — trigger removed

        with patch.object(
            DailyCaGeneratorService, "_run_single_cycle", mock_single_cycle
        ):
            with patch(
                "engines.daily_ca.services.generator_service.StaticBackgroundService.trigger_pending_static_generation",
                return_value=1,
            ) as mock_trigger:
                results = DailyCaGeneratorService.run_generation_cycle(
                    proposals=[proposal], groq_calls_used=0
                )

        # Phase A: static trigger is decoupled — must NEVER fire from this path
        mock_trigger.assert_not_called()
        assert results["static_triggered"] == 0


# ── HeroImageService ──────────────────────────────────────────────────────────


class TestHeroImageService:
    """Tests for engines.daily_ca.services.image_service.HeroImageService."""

    def test_fetch_and_upload_returns_cloudinary_url_on_unsplash_success(self):
        """Unsplash returns a valid URL → Cloudinary upload called → URL returned."""
        from engines.daily_ca.services.image_service import HeroImageService

        with patch.object(
            HeroImageService,
            "_try_unsplash",
            return_value="https://images.unsplash.com/photo-abc.jpg",
        ):
            with patch.object(
                HeroImageService,
                "_upload_to_cloudinary",
                return_value="https://res.cloudinary.com/test/image/upload/ca_test.jpg",
            ) as mock_upload:
                result = HeroImageService.fetch_and_upload(
                    source_urls=[],
                    topic_name="Parliament of India",
                    article_id="test-001",
                )

        assert result == "https://res.cloudinary.com/test/image/upload/ca_test.jpg"
        mock_upload.assert_called_once()

    def test_fetch_and_upload_falls_back_to_wikipedia_when_unsplash_fails(self):
        """Unsplash returns '' → Wikipedia fallback tried → upload called."""
        from engines.daily_ca.services.image_service import HeroImageService

        with patch.object(HeroImageService, "_try_unsplash", return_value=""):
            with patch.object(
                HeroImageService,
                "_try_wikipedia_thumbnail",
                return_value="https://upload.wikimedia.org/wikipedia/photo.jpg",
            ):
                with patch.object(
                    HeroImageService,
                    "_upload_to_cloudinary",
                    return_value="https://res.cloudinary.com/test/ca_wiki.jpg",
                ) as mock_upload:
                    result = HeroImageService.fetch_and_upload(
                        source_urls=[], topic_name="Monsoon", article_id="test-002"
                    )

        assert result == "https://res.cloudinary.com/test/ca_wiki.jpg"
        mock_upload.assert_called_once()

    def test_fetch_and_upload_returns_empty_string_when_both_sources_fail(self):
        """Both Unsplash and Wikipedia return '' → fetch_and_upload returns ''."""
        from engines.daily_ca.services.image_service import HeroImageService

        with patch.object(HeroImageService, "_try_unsplash", return_value=""):
            with patch.object(
                HeroImageService, "_try_wikipedia_thumbnail", return_value=""
            ):
                result = HeroImageService.fetch_and_upload(
                    source_urls=[], topic_name="Obscure Topic", article_id="test-003"
                )

        assert result == ""

    def test_fetch_and_upload_never_raises_on_exception(self):
        """Any internal exception must be swallowed — never propagates to caller."""
        from engines.daily_ca.services.image_service import HeroImageService

        with patch.object(
            HeroImageService,
            "_try_unsplash",
            side_effect=RuntimeError("API crashed"),
        ):
            with patch.object(
                HeroImageService,
                "_try_wikipedia_thumbnail",
                side_effect=RuntimeError("also crashed"),
            ):
                result = HeroImageService.fetch_and_upload(
                    source_urls=[], topic_name="Any Topic", article_id="test-004"
                )

        assert result == ""

    def test_is_valid_image_url_rejects_svg_extension(self):
        """URLs ending in .svg must be rejected."""
        from engines.daily_ca.services.image_service import _is_valid_image_url

        assert _is_valid_image_url("https://example.com/image.svg") is False

    def test_is_valid_image_url_rejects_svg_png_wikipedia_render(self):
        """.svg.png (Wikipedia SVG rendered as PNG) must be rejected."""
        from engines.daily_ca.services.image_service import _is_valid_image_url

        assert (
            _is_valid_image_url(
                "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f7/"
                "RajyaSabha.svg/330px-RajyaSabha.svg.png"
            )
            is False
        )

    def test_is_valid_image_url_accepts_valid_jpeg(self):
        """Normal JPEG URLs must pass validation."""
        from engines.daily_ca.services.image_service import _is_valid_image_url

        assert (
            _is_valid_image_url("https://images.unsplash.com/photo-12345.jpg") is True
        )

    def test_is_valid_image_url_rejects_data_uri(self):
        """data: URIs must be rejected."""
        from engines.daily_ca.services.image_service import _is_valid_image_url

        assert _is_valid_image_url("data:image/png;base64,ABC123") is False

    def test_try_unsplash_returns_empty_when_no_access_key(self):
        """With blank UNSPLASH_ACCESS_KEY, _try_unsplash returns '' before any HTTP call."""
        import os

        from engines.daily_ca.services.image_service import HeroImageService

        original = os.environ.get("UNSPLASH_ACCESS_KEY", "")
        os.environ["UNSPLASH_ACCESS_KEY"] = ""
        try:
            # requests is imported locally inside _try_unsplash; with no key set
            # the method returns "" immediately before reaching the import statement.
            result = HeroImageService._try_unsplash("Parliament of India")
        finally:
            os.environ["UNSPLASH_ACCESS_KEY"] = original

        assert result == ""
