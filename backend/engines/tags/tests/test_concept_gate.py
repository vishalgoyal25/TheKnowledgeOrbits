"""
engines/tags/tests/test_concept_gate.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
G3.11 — the generator refuses to save a body the sitemap would refuse to list.
G3.12 — the regeneration queue rewrites thin READY pages in place, never worse.

Pins the two properties the G0.3 audit (§4.3) demanded:
  1. the `thin` count cannot GROW — a failing draft leaves the stub a stub;
  2. regeneration can only IMPROVE a page — a failing rewrite keeps the old body.
"""

from io import StringIO
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings

import pytest

from engines.tags.models import ConceptPage
from engines.tags.services.concept_content_service import (
    ConceptContentService,
    trim_to_paragraphs,
)
from engines.tags.services.concept_seo_service import (
    MAX_WORDS,
    needs_regeneration,
    quality_issues,
)

SECTION = "## Section {i}\n\n" + ("fact " * 150).strip()
GOOD_BODY = "Opening paragraph.\n\n" + "\n\n".join(
    SECTION.format(i=i) for i in range(1, 4)
)  # 3 headings, ~450 words, real line breaks
THIN_BODY = "word " * 600  # ~600 words, zero headings, ONE line — the C7 shape
SHORT_BODY = "## A\n\n## B\n\n## C\n\nfew words."

LLM = "engines.tags.services.concept_content_service.llm_call"
LOCMEM = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "concept-gate-tests",
    }
}


def _concept(slug: str, body: str = "", ready: bool = False, usage: int = 0):
    return ConceptPage.objects.create(
        name=slug.replace("-", " ").title(),
        slug=slug,
        brief_description="brief",
        body_md=body,
        is_content_ready=ready,
        usage_count=usage,
    )


# ── The rule itself ──────────────────────────────────────────────────────────


class TestQualityIssues:
    def test_good_body_passes(self):
        assert quality_issues(GOOD_BODY) == []

    def test_short_body_named(self):
        assert any(i.startswith("words") for i in quality_issues(SHORT_BODY))

    def test_zero_headings_named(self):
        body = "para. " * 500
        body = "\n\n".join([body[:1000], body[1000:2000]])
        assert any(i.startswith("headings") for i in quality_issues(body))

    def test_single_line_body_is_the_c7_shape(self):
        assert any("no newline" in i for i in quality_issues(THIN_BODY))

    def test_rambling_body_named(self):
        long = GOOD_BODY + "\n\n" + ("more " * (MAX_WORDS + 50))
        assert any("> " in i for i in quality_issues(long))


class TestTrim:
    def test_trim_keeps_paragraphs_and_headings(self):
        long = GOOD_BODY + "\n\n" + "## Tail\n\n" + ("tail " * (MAX_WORDS + 100))
        trimmed = trim_to_paragraphs(long)
        assert trimmed.startswith("Opening paragraph.")
        assert trimmed.count("\n## ") >= 3
        assert quality_issues(trimmed) == []


# ── G3.11: the generator ────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGeneratorGate:
    def test_good_draft_is_saved(self):
        c = _concept("good")
        with patch(LLM, return_value=GOOD_BODY) as llm:
            assert ConceptContentService.generate_concept_content(c) is True
        c.refresh_from_db()
        assert c.is_content_ready is True
        # The stored sitemap flag follows a partial save (update_fields) too.
        assert c.is_indexable is True
        assert llm.call_count == 1

    def test_bad_then_good_uses_one_retry(self):
        c = _concept("retry")
        with patch(LLM, side_effect=[THIN_BODY, GOOD_BODY]) as llm:
            assert ConceptContentService.generate_concept_content(c) is True
        c.refresh_from_db()
        assert c.is_content_ready is True
        assert llm.call_count == 2
        # The retry prompt carries the measured failure back to the model.
        assert "REJECTED" in llm.call_args_list[1].args[0]

    def test_two_bad_drafts_leave_the_stub_a_stub(self):
        c = _concept("stub")
        with patch(LLM, side_effect=[THIN_BODY, SHORT_BODY]) as llm:
            assert ConceptContentService.generate_concept_content(c) is False
        c.refresh_from_db()
        assert c.is_content_ready is False
        assert c.body_md == ""
        assert llm.call_count == 2

    def test_forced_rewrite_that_fails_keeps_the_old_body(self):
        c = _concept("thin", body=THIN_BODY, ready=True)
        with patch(LLM, return_value=SHORT_BODY):
            assert (
                ConceptContentService.generate_concept_content(c, force=True) is False
            )
        c.refresh_from_db()
        assert c.body_md == THIN_BODY
        assert c.is_content_ready is True

    def test_ready_page_is_skipped_without_force(self):
        c = _concept("locked", body=GOOD_BODY, ready=True)
        with patch(LLM) as llm:
            assert ConceptContentService.generate_concept_content(c) is False
        assert llm.call_count == 0


# ── G3.12: the queue and the command ────────────────────────────────────────


@pytest.mark.django_db
class TestRegenerationQueue:
    def test_membership(self):
        assert needs_regeneration(_concept("a", THIN_BODY, ready=True)) is True
        assert needs_regeneration(_concept("b", GOOD_BODY, ready=True)) is False
        assert needs_regeneration(_concept("c", "", ready=False)) is False

    @override_settings(CACHES=LOCMEM)
    def test_kill_switch_off_does_nothing(self, monkeypatch):
        monkeypatch.delenv("CONCEPT_REGENERATION_ENABLED", raising=False)
        _concept("thin", THIN_BODY, ready=True)
        out = StringIO()
        with patch(LLM) as llm:
            call_command("regenerate_concept_content", stdout=out)
        assert "is off" in out.getvalue()
        assert llm.call_count == 0

    @override_settings(CACHES=LOCMEM)
    def test_dry_run_lists_without_writing(self):
        _concept("thin", THIN_BODY, ready=True)
        out = StringIO()
        with patch(LLM) as llm:
            call_command("regenerate_concept_content", dry_run=True, stdout=out)
        assert "would rewrite thin" in out.getvalue()
        assert llm.call_count == 0

    @override_settings(CACHES=LOCMEM)
    def test_manual_run_rewrites_broken_first_under_max(self):
        cache.clear()
        _concept("good", GOOD_BODY, ready=True)
        _concept("thin-popular", "## A\n\nshort.", ready=True, usage=50)
        broken = _concept("broken", THIN_BODY, ready=True, usage=1)
        out = StringIO()
        with patch(LLM, return_value=GOOD_BODY) as llm:
            call_command("regenerate_concept_content", max=1, manual=True, stdout=out)
        assert llm.call_count == 1
        broken.refresh_from_db()
        assert broken.body_md == GOOD_BODY  # the single-line page went first
        assert "Rewritten 1" in out.getvalue()
        assert cache.get("tags:regenerate_concept_content:lock") is None
