"""
engines/book_content/tests/test_models.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase H — Model Unit Tests

Covers:
  - BookPlan.__str__ and generation_status default
  - BookContent.__str__ and auto word_count on save
  - TopicRelation.__str__ and unique_together IntegrityError
  - CrossReference.__str__
  - GenerationLog.__str__ and default ordering (-created_at)

All tests use Django's TestCase (wrapped in a DB transaction → auto rollback).
No mocking required — these are pure ORM + model logic tests.
"""

from __future__ import annotations

from django.db import IntegrityError
from django.test import TestCase

from engines.book_content.models import (
    BookContent,
    BookPlan,
    CrossReference,
    GenerationLog,
    TopicRelation,
)
from engines.knowledge.models import Module, Program, Subject, Topic


# ─────────────────────────────────────────────────────────────────────────────
# SHARED FIXTURE HELPER
# ─────────────────────────────────────────────────────────────────────────────


def _make_hierarchy(suffix: str = "") -> tuple[Subject, Module, Topic, Topic]:
    """
    Creates the minimal knowledge hierarchy needed for FK dependencies.
    Uses a suffix to avoid unique-name collisions across test classes.
    Returns: (subject, module, topic1, topic2)
    """
    program = Program.objects.create(
        name=f"Test Program{suffix}",
        description="Phase H test program",
    )
    subject = Subject.objects.create(
        name=f"Test Subject{suffix}",
        program=program,
        description="Phase H test subject",
        is_active=True,
    )
    module = Module.objects.create(
        name=f"Test Module{suffix}",
        subject=subject,
        description="Phase H test module",
        is_active=True,
        order_index=0,
    )
    topic = Topic.objects.create(
        name=f"Test Topic A{suffix}",
        module=module,
        subject=subject,
        is_active=True,
        topic_type="syllabus",
        order_index=0,
    )
    topic2 = Topic.objects.create(
        name=f"Test Topic B{suffix}",
        module=module,
        subject=subject,
        is_active=True,
        topic_type="syllabus",
        order_index=1,
    )
    return subject, module, topic, topic2


# ─────────────────────────────────────────────────────────────────────────────
# BookPlan
# ─────────────────────────────────────────────────────────────────────────────


class TestBookPlan(TestCase):
    """Tests for the BookPlan model."""

    def setUp(self) -> None:
        self.subject, _, _, _ = _make_hierarchy("_bp")

    def test_str_includes_subject_name_and_status(self) -> None:
        """BookPlan.__str__ returns 'BookPlan: <subject> (<status>)'."""
        plan = BookPlan.objects.create(
            subject=self.subject,
            generation_status="generating",
        )
        assert str(plan) == "BookPlan: Test Subject_bp (generating)"

    def test_generation_status_defaults_to_planned(self) -> None:
        """BookPlan.generation_status field default is 'planned'."""
        plan = BookPlan.objects.create(subject=self.subject)
        assert plan.generation_status == "planned"

    def test_str_with_planned_status(self) -> None:
        """BookPlan.__str__ works correctly with default planned status."""
        plan = BookPlan.objects.create(subject=self.subject)
        assert "(planned)" in str(plan)
        assert "Test Subject_bp" in str(plan)


# ─────────────────────────────────────────────────────────────────────────────
# BookContent
# ─────────────────────────────────────────────────────────────────────────────


class TestBookContent(TestCase):
    """Tests for the BookContent model."""

    def setUp(self) -> None:
        self.subject, _, self.topic, self.topic2 = _make_hierarchy("_bc")

    def test_str_includes_topic_name_and_quality_score(self) -> None:
        """BookContent.__str__ returns 'BookContent: <topic> (score=<N>)'."""
        bc = BookContent.objects.create(
            topic=self.topic,
            subject=self.subject,
            content_markdown="some content",
            quality_score=87.0,
        )
        assert str(bc) == "BookContent: Test Topic A_bc (score=87)"

    def test_save_auto_computes_word_count(self) -> None:
        """BookContent.save() sets word_count = len(content_markdown.split())."""
        bc = BookContent(
            topic=self.topic,
            subject=self.subject,
            content_markdown="one two three four five",
        )
        bc.save()
        assert bc.word_count == 5

    def test_word_count_updates_on_subsequent_save(self) -> None:
        """word_count is recomputed every time save() is called."""
        bc = BookContent.objects.create(
            topic=self.topic,
            subject=self.subject,
            content_markdown="one two three",
        )
        assert bc.word_count == 3

        bc.content_markdown = "one two three four five six seven"
        bc.save()
        assert bc.word_count == 7

    def test_word_count_zero_for_empty_content(self) -> None:
        """word_count stays 0 when content_markdown is empty string."""
        bc = BookContent.objects.create(
            topic=self.topic,
            subject=self.subject,
            content_markdown="",
        )
        # empty string: "".split() == [] → word_count stays at default 0
        assert bc.word_count == 0

    def test_word_count_handles_extra_whitespace(self) -> None:
        """split() collapses whitespace — word_count is accurate."""
        bc = BookContent.objects.create(
            topic=self.topic,
            subject=self.subject,
            content_markdown="  word1   word2\nword3\t\tword4  ",
        )
        assert bc.word_count == 4


# ─────────────────────────────────────────────────────────────────────────────
# TopicRelation
# ─────────────────────────────────────────────────────────────────────────────


class TestTopicRelation(TestCase):
    """Tests for the TopicRelation model."""

    def setUp(self) -> None:
        _, _, self.topic, self.topic2 = _make_hierarchy("_tr")

    def test_str_shows_source_relation_type_and_target(self) -> None:
        """TopicRelation.__str__ format: 'A →[type]→ B'."""
        rel = TopicRelation.objects.create(
            source_topic=self.topic,
            target_topic=self.topic2,
            relation_type="related_to",
        )
        s = str(rel)
        assert "Test Topic A_tr" in s
        assert "related_to" in s
        assert "Test Topic B_tr" in s

    def test_unique_together_raises_integrity_error_on_duplicate(self) -> None:
        """Inserting the same (source_topic, target_topic) pair twice raises IntegrityError."""
        TopicRelation.objects.create(
            source_topic=self.topic,
            target_topic=self.topic2,
            relation_type="related_to",
        )
        with self.assertRaises(IntegrityError):
            TopicRelation.objects.create(
                source_topic=self.topic,
                target_topic=self.topic2,
                relation_type="cross_subject",  # different type, same pair → still violates unique
            )

    def test_relation_type_default_is_related_to(self) -> None:
        """TopicRelation.relation_type defaults to 'related_to'."""
        rel = TopicRelation.objects.create(
            source_topic=self.topic,
            target_topic=self.topic2,
        )
        assert rel.relation_type == "related_to"


# ─────────────────────────────────────────────────────────────────────────────
# CrossReference
# ─────────────────────────────────────────────────────────────────────────────


class TestCrossReference(TestCase):
    """Tests for the CrossReference model."""

    def setUp(self) -> None:
        self.subject, _, self.topic, self.topic2 = _make_hierarchy("_cr")
        self.bc1 = BookContent.objects.create(
            topic=self.topic,
            subject=self.subject,
            content_markdown="Article one content",
        )
        self.bc2 = BookContent.objects.create(
            topic=self.topic2,
            subject=self.subject,
            content_markdown="Article two content",
        )

    def test_str_shows_source_and_target_topic_names(self) -> None:
        """CrossReference.__str__ format: 'CrossRef: <source topic> → <target topic>'."""
        xref = CrossReference.objects.create(
            source_content=self.bc1,
            target_content=self.bc2,
            ref_type="see_also",
        )
        s = str(xref)
        assert "Test Topic A_cr" in s
        assert "Test Topic B_cr" in s

    def test_unique_together_raises_on_duplicate(self) -> None:
        """CrossReference unique_together (source_content, target_content) raises IntegrityError."""
        CrossReference.objects.create(
            source_content=self.bc1,
            target_content=self.bc2,
        )
        with self.assertRaises(IntegrityError):
            CrossReference.objects.create(
                source_content=self.bc1,
                target_content=self.bc2,
            )


# ─────────────────────────────────────────────────────────────────────────────
# GenerationLog
# ─────────────────────────────────────────────────────────────────────────────


class TestGenerationLog(TestCase):
    """Tests for the GenerationLog model."""

    def test_str_includes_topic_name_status_and_score(self) -> None:
        """GenerationLog.__str__ returns 'GenLog: <topic> [<status>] score=<N>'."""
        log = GenerationLog.objects.create(
            topic_name="Parliament of India",
            subject_name="Indian Polity",
            status="success",
            quality_score=82.0,
        )
        s = str(log)
        assert "Parliament of India" in s
        assert "success" in s
        assert "82" in s

    def test_default_ordering_newest_first(self) -> None:
        """GenerationLog Meta.ordering = ['-created_at'] — newest record appears first."""
        log1 = GenerationLog.objects.create(
            topic_name="Alpha Topic",
            subject_name="Sub",
            status="success",
        )
        log2 = GenerationLog.objects.create(
            topic_name="Beta Topic",
            subject_name="Sub",
            status="success",
        )
        logs = list(
            GenerationLog.objects.filter(topic_name__in=["Alpha Topic", "Beta Topic"])
        )
        # Beta was created after Alpha → Beta should appear first (newest first)
        assert logs[0].id == log2.id
        assert logs[1].id == log1.id

    def test_status_field_stores_correctly(self) -> None:
        """GenerationLog.status field stores and retrieves the given value."""
        for status in ("success", "failed", "skipped"):
            log = GenerationLog.objects.create(
                topic_name=f"Topic {status}",
                subject_name="Sub",
                status=status,
            )
            assert log.status == status
