"""Knowledge Engine - Model Tests"""

import pytest

from engines.content.models import Chunk, Document
from engines.knowledge.models import ChunkTopicMap, Module, Program, Subject, Topic


@pytest.mark.django_db
class TestProgramModel:
    def test_create_program(self):
        program = Program.objects.create(
            name="UPSC CSE", description="Civil Services Examination"
        )
        assert program.name == "UPSC CSE"
        assert program.is_active

    def test_program_unique_name(self):
        Program.objects.create(name="UPSC CSE")
        with pytest.raises(Exception):  # IntegrityError
            Program.objects.create(name="UPSC CSE")


@pytest.mark.django_db
class TestSubjectModel:
    def test_create_subject(self):
        program = Program.objects.create(name="UPSC CSE")
        subject = Subject.objects.create(name="Polity", program=program, order_index=1)
        assert subject.name == "Polity"
        assert subject.program == program

    def test_unique_program_subject_name(self):
        program = Program.objects.create(name="UPSC CSE")
        Subject.objects.create(name="Polity", program=program)

        with pytest.raises(Exception):  # IntegrityError
            Subject.objects.create(name="Polity", program=program)


@pytest.mark.django_db
class TestModuleModel:
    def test_create_module(self):
        program = Program.objects.create(name="UPSC CSE")
        subject = Subject.objects.create(name="Polity", program=program)
        module = Module.objects.create(
            name="Fundamental Rights", subject=subject, order_index=1
        )
        assert module.name == "Fundamental Rights"
        assert module.subject == subject


@pytest.mark.django_db
class TestTopicModel:
    def test_create_topic(self):
        program = Program.objects.create(name="UPSC CSE")
        subject = Subject.objects.create(name="Polity", program=program)
        module = Module.objects.create(name="Constitution", subject=subject)

        topic = Topic.objects.create(
            name="Article 370",
            module=module,
            subject=subject,
            difficulty_level="medium",
        )

        assert topic.name == "Article 370"
        assert topic.difficulty_level == "medium"

    def test_topic_with_parent(self):
        program = Program.objects.create(name="UPSC CSE")
        subject = Subject.objects.create(name="Polity", program=program)
        module = Module.objects.create(name="Constitution", subject=subject)

        parent = Topic.objects.create(
            name="Fundamental Rights", module=module, subject=subject
        )
        child = Topic.objects.create(
            name="Right to Equality",
            module=module,
            subject=subject,
            parent_topic=parent,
        )

        assert child.parent_topic == parent
        assert parent.subtopics.count() == 1


@pytest.mark.django_db
class TestSlugs:
    """G3.10 — slugs are minted once, globally unique per model, never rewritten."""

    def _tree(self):
        program = Program.objects.create(name="UPSC CSE")
        subject = Subject.objects.create(
            name="Indian Polity & Constitution", program=program
        )
        module = Module.objects.create(name="Fundamental Rights", subject=subject)
        return program, subject, module

    def test_slug_minted_on_create_for_all_three(self):
        _, subject, module = self._tree()
        topic = Topic.objects.create(
            name="Article 32: Writs", module=module, subject=subject
        )

        assert subject.slug == "indian-polity-constitution"
        assert module.slug == "fundamental-rights"
        assert topic.slug == "article-32-writs"

    def test_collision_takes_next_numeric_suffix(self):
        program, subject, _ = self._tree()
        other_subject = Subject.objects.create(name="Indian Economy", program=program)

        first = Module.objects.create(name="Introduction", subject=subject)
        second = Module.objects.create(name="Introduction", subject=other_subject)
        third = Module.objects.create(name="Introduction!", subject=subject)

        assert first.slug == "introduction"
        assert second.slug == "introduction-2"
        assert third.slug == "introduction-3"

    def test_rename_does_not_rewrite_slug(self):
        _, subject, module = self._tree()
        topic = Topic.objects.create(name="Old Name", module=module, subject=subject)
        assert topic.slug == "old-name"

        topic.name = "Completely New Name"
        topic.save()
        topic.refresh_from_db()

        assert topic.slug == "old-name"

    def test_explicit_slug_is_kept(self):
        _, subject, module = self._tree()
        topic = Topic.objects.create(
            name="Anything", slug="hand-picked", module=module, subject=subject
        )
        assert topic.slug == "hand-picked"


@pytest.mark.django_db
class TestChunkTopicMapModel:
    def test_create_mapping(self):
        program = Program.objects.create(name="UPSC CSE")
        subject = Subject.objects.create(name="Polity", program=program)
        module = Module.objects.create(name="Constitution", subject=subject)
        topic = Topic.objects.create(name="Article 370", module=module, subject=subject)

        doc = Document.objects.create(
            title="Test Doc", file_path="/test.pdf", source_type="static"
        )
        chunk = Chunk.objects.create(
            chunk_text="Test content", chunk_index=0, source_type="static", document=doc
        )

        mapping = ChunkTopicMap.objects.create(
            chunk=chunk, topic=topic, relevance_score=0.85, priority=1
        )

        assert mapping.relevance_score == 0.85
        assert mapping.priority == 1

    def test_unique_chunk_topic_mapping(self):
        program = Program.objects.create(name="UPSC CSE")
        subject = Subject.objects.create(name="Polity", program=program)
        module = Module.objects.create(name="Constitution", subject=subject)
        topic = Topic.objects.create(name="Article 370", module=module, subject=subject)

        doc = Document.objects.create(
            title="Test Doc", file_path="/test.pdf", source_type="static"
        )
        chunk = Chunk.objects.create(
            chunk_text="Test", chunk_index=0, source_type="static", document=doc
        )

        ChunkTopicMap.objects.create(chunk=chunk, topic=topic)

        with pytest.raises(Exception):  # IntegrityError
            ChunkTopicMap.objects.create(chunk=chunk, topic=topic)
