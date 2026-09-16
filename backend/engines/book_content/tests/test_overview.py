"""
engines/book_content/tests/test_overview.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
G3.9 — subject/module overviews (FEATURES_GROWTH_STACK.md §7.9a).

Pins the safety properties, not the prose:
  - the queue is ONE subject + its modules, children-gated, recomputed per run
  - a failing draft writes nothing; a passing one lands as a draft
  - the hierarchy tables are untouched by a run
  - the kill switch, the lock and the pre-flight each stop a run cold
  - the endpoint serves only published rows, by slug or UUID
"""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command

import pytest
from rest_framework.test import APIClient

from engines.book_content.models import BookContent, OverviewContent
from engines.book_content.services import overview_service as svc
from engines.knowledge.models import Module, Program, Subject, Topic

SECTION = "## Part {i}\n\n" + ("fact " * 120).strip()
GOOD = "Opening.\n\n" + "\n\n".join(SECTION.format(i=i) for i in (1, 2))  # ~240 w, 2 h
BAD = "short " * 40  # one line, 40 words

LLM = "engines.book_content.services.overview_service.llm_call"
HEALTH = (
    "engines.book_content.management.commands.generate_overview_content."
    "check_any_llm_available"
)
LOCMEM = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "overview-tests",
    }
}


def _tree(with_article: bool = True):
    program = Program.objects.create(name="P", description="p")
    s1 = Subject.objects.create(name="Polity", program=program, order_index=0)
    s2 = Subject.objects.create(name="History", program=program, order_index=1)
    m1 = Module.objects.create(name="Constitution", subject=s1, order_index=0)
    m2 = Module.objects.create(name="Parliament", subject=s1, order_index=1)
    t1 = Topic.objects.create(name="Preamble", module=m1, subject=s1, order_index=0)
    Topic.objects.create(name="Lok Sabha", module=m2, subject=s1, order_index=0)
    if with_article:
        BookContent.objects.create(
            topic=t1,
            subject=s1,
            content_markdown="## Intro\n\nThe Preamble declares the ideals.\n\nMore.",
            quality_score=80,
            is_published=True,
        )
    return s1, s2, m1, m2


# ── Queue ────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestQueue:
    def test_one_subject_and_its_grounded_modules(self):
        s1, s2, m1, m2 = _tree()
        keys = [t.key for t in svc.next_subject_batch()]
        # Polity (has an article) + Constitution (has one); Parliament has
        # none yet → skipped; History has none anywhere → not this run.
        assert keys == [f"subject:{s1.id}", f"module:{m1.id}"]

    def test_finishes_a_half_done_branch_before_moving_on(self):
        s1, s2, m1, m2 = _tree()
        OverviewContent.objects.create(
            target_type="subject", target_id=s1.id, content_markdown=GOOD
        )
        OverviewContent.objects.create(
            target_type="module", target_id=m1.id, content_markdown=GOOD
        )
        # Parliament gains an article later → it is picked up, not History.
        BookContent.objects.create(
            topic=Topic.objects.get(name="Lok Sabha"),
            subject=s1,
            content_markdown="Body.",
        )
        assert [t.key for t in svc.next_subject_batch()] == [f"module:{m2.id}"]

    def test_empty_tree_yields_nothing(self):
        _tree(with_article=False)
        assert svc.next_subject_batch() == []

    def test_prompt_is_grounded_on_article_names(self):
        s1, *_ = _tree()
        target = svc.next_subject_batch()[0]
        prompt, grounded = svc.build_prompt(target)
        assert grounded == 1
        assert "Preamble — The Preamble declares" in prompt
        assert "Constitution; Parliament" in prompt  # modules in syllabus order


# ── Generation ───────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGenerate:
    def test_passing_draft_lands_as_draft(self):
        _tree()
        target = svc.next_subject_batch()[0]
        with patch(LLM, return_value=GOOD):
            row = svc.generate_overview(target)
        assert row is not None
        assert row.is_published is False
        assert row.grounded_on == 1
        assert row.generation_pass == 1

    def test_two_bad_drafts_write_nothing(self):
        _tree()
        target = svc.next_subject_batch()[0]
        with patch(LLM, return_value=BAD) as llm:
            assert svc.generate_overview(target) is None
        assert llm.call_count == 2
        assert OverviewContent.objects.count() == 0

    def test_hierarchy_is_untouched(self):
        _tree()
        before = (
            list(Subject.objects.values_list("id", "name", "order_index")),
            list(Module.objects.values_list("id", "name", "order_index")),
            list(Topic.objects.values_list("id", "name", "content_status")),
        )
        with patch(LLM, return_value=GOOD):
            for t in svc.next_subject_batch():
                svc.generate_overview(t)
        after = (
            list(Subject.objects.values_list("id", "name", "order_index")),
            list(Module.objects.values_list("id", "name", "order_index")),
            list(Topic.objects.values_list("id", "name", "content_status")),
        )
        assert before == after


# ── Command ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCommand:
    @pytest.fixture(autouse=True)
    def _locmem(self, settings):
        # override_settings cannot decorate a plain pytest class; the fixture
        # fires Django's setting_changed signal, which resets the cache handler.
        settings.CACHES = LOCMEM

    def test_kill_switch_off(self, monkeypatch):
        monkeypatch.delenv("OVERVIEW_GENERATION_ENABLED", raising=False)
        _tree()
        out = StringIO()
        with patch(LLM) as llm:
            call_command("generate_overview_content", stdout=out)
        assert "is off" in out.getvalue()
        assert llm.call_count == 0

    def test_no_llm_skips(self):
        _tree()
        out = StringIO()
        with patch(HEALTH, return_value=False), patch(LLM) as llm:
            call_command("generate_overview_content", manual=True, stdout=out)
        assert "No LLM" in out.getvalue()
        assert llm.call_count == 0

    def test_lock_held_exits(self):
        _tree()
        cache.clear()
        cache.add("overview_generation_lock", "1", timeout=60)
        out = StringIO()
        with patch(HEALTH, return_value=True), patch(LLM) as llm:
            call_command("generate_overview_content", manual=True, stdout=out)
        assert "lock" in out.getvalue()
        assert llm.call_count == 0
        cache.delete("overview_generation_lock")

    def test_manual_run_writes_subject_and_module_then_releases_lock(self):
        s1, s2, m1, m2 = _tree()
        cache.clear()
        out = StringIO()
        with patch(HEALTH, return_value=True), patch(LLM, return_value=GOOD):
            call_command("generate_overview_content", manual=True, stdout=out)
        assert OverviewContent.objects.filter(target_id=s1.id).exists()
        assert OverviewContent.objects.filter(target_id=m1.id).exists()
        assert not OverviewContent.objects.filter(target_id=m2.id).exists()
        assert OverviewContent.objects.filter(is_published=True).count() == 0
        assert cache.get("overview_generation_lock") is None
        assert "Written 2" in out.getvalue()

    def test_dry_run_writes_nothing(self):
        _tree()
        out = StringIO()
        with patch(LLM) as llm:
            call_command("generate_overview_content", dry_run=True, stdout=out)
        assert "would write subject:" in out.getvalue()
        assert llm.call_count == 0
        assert OverviewContent.objects.count() == 0


# ── Endpoint ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEndpoint:
    @pytest.fixture(autouse=True)
    def _locmem(self, settings):
        settings.CACHES = LOCMEM

    def test_draft_is_404_published_is_200_by_slug_and_uuid(self):
        cache.clear()
        s1, *_ = _tree()
        row = OverviewContent.objects.create(
            target_type="subject", target_id=s1.id, content_markdown=GOOD
        )
        client = APIClient()
        assert (
            client.get(f"/api/v1/book/overview/subject/{s1.slug}/").status_code == 404
        )
        row.is_published = True
        row.save()
        by_slug = client.get(f"/api/v1/book/overview/subject/{s1.slug}/")
        assert by_slug.status_code == 200
        assert by_slug.data["target_name"] == "Polity"
        assert by_slug.data["target_slug"] == s1.slug
        assert by_slug.data["content_markdown"].startswith("Opening.")
        assert client.get(f"/api/v1/book/overview/subject/{s1.id}/").status_code == 200

    def test_unknown_type_is_404(self):
        assert APIClient().get("/api/v1/book/overview/topic/x/").status_code == 404
