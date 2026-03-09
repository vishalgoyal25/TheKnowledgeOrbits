"""
Knowledge Engine Serializers
"""

from typing import Any

from rest_framework import serializers

from engines.knowledge.models import (
    ChunkTopicMap,
    Module,
    Program,
    Subject,
    Theme,
    ThemeTopicMap,
    Topic,
)


class ProgramListSerializer(serializers.ModelSerializer):  # type: ignore
    """Lightweight serializer for Program listing."""

    class Meta:
        model = Program
        fields = [
            "id",
            "name",
            "is_active",
            "created_at",
        ]
        read_only_fields = fields


class ProgramSerializer(serializers.ModelSerializer):  # type: ignore
    """Serializer for Program detail."""

    subjects_count = serializers.IntegerField(source="subjects.count", read_only=True)

    class Meta:
        model = Program
        fields = [
            "id",
            "name",
            "description",
            "exam_pattern",
            "is_active",
            "subjects_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "subjects_count", "created_at", "updated_at"]


class SubjectListSerializer(serializers.ModelSerializer):  # type: ignore
    """Lightweight serializer for Subject listing."""

    program_name = serializers.CharField(source="program.name", read_only=True)

    class Meta:
        model = Subject
        fields = [
            "id",
            "name",
            "program",
            "program_name",
            "order_index",
            "is_active",
        ]
        read_only_fields = fields


class SubjectSerializer(serializers.ModelSerializer):  # type: ignore
    """Serializer for Subject detail."""

    program_name = serializers.CharField(source="program.name", read_only=True)
    modules_count = serializers.IntegerField(source="modules.count", read_only=True)

    class Meta:
        model = Subject
        fields = [
            "id",
            "name",
            "program",
            "program_name",
            "description",
            "order_index",
            "is_active",
            "modules_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "program_name",
            "modules_count",
            "created_at",
            "updated_at",
        ]


class ModuleListSerializer(serializers.ModelSerializer):  # type: ignore
    """Lightweight serializer for Module listing."""

    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = Module
        fields = [
            "id",
            "name",
            "subject",
            "subject_name",
            "order_index",
            "is_active",
        ]
        read_only_fields = fields


class ModuleSerializer(serializers.ModelSerializer):  # type: ignore
    """Serializer for Module detail."""

    subject_name = serializers.CharField(source="subject.name", read_only=True)
    topics_count = serializers.IntegerField(source="topics.count", read_only=True)

    class Meta:
        model = Module
        fields = [
            "id",
            "name",
            "subject",
            "subject_name",
            "description",
            "order_index",
            "is_active",
            "topics_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "subject_name",
            "topics_count",
            "created_at",
            "updated_at",
        ]


class TopicListSerializer(serializers.ModelSerializer):  # type: ignore
    """Lightweight serializer for Topic listing (prevents N+1 counts)."""

    module_name = serializers.CharField(source="module.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = Topic
        fields = [
            "id",
            "name",
            "module",
            "module_name",
            "subject",
            "subject_name",
            "parent_topic",
            "topic_type",
            "difficulty_level",
            "order_index",
            "is_active",
            "created_at",
        ]
        read_only_fields = fields


class TopicSerializer(serializers.ModelSerializer):  # type: ignore
    """Serializer for Topic detail."""

    module_name = serializers.CharField(source="module.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    chunks_count = serializers.IntegerField(
        source="chunk_mappings.count", read_only=True
    )

    class Meta:
        model = Topic
        fields = [
            "id",
            "name",
            "module",
            "module_name",
            "subject",
            "subject_name",
            "parent_topic",
            "description",
            "keywords",
            "topic_type",
            "difficulty_level",
            "order_index",
            "is_active",
            "chunks_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "module_name",
            "subject_name",
            "chunks_count",
            "created_at",
            "updated_at",
        ]


class ChunkTopicMapSerializer(serializers.ModelSerializer):  # type: ignore
    """Serializer for ChunkTopicMap."""

    topic_name = serializers.CharField(source="topic.name", read_only=True)
    chunk_text_preview = serializers.SerializerMethodField()

    def get_chunk_text_preview(self, obj) -> Any:  # type: ignore
        """Get chunk text preview (first 200 chars)."""
        text = obj.chunk.chunk_text
        return text[:200] + "..." if len(text) > 200 else text

    class Meta:
        model = ChunkTopicMap
        fields = [
            "id",
            "chunk",
            "chunk_text_preview",
            "topic",
            "topic_name",
            "relevance_score",
            "priority",
            "auto_mapped",
            "approved_by",
            "created_at",
        ]
        read_only_fields = ["id", "topic_name", "chunk_text_preview", "created_at"]


class ThemeSerializer(serializers.ModelSerializer):  # type: ignore
    """Serializer for Theme."""

    topics_count = serializers.IntegerField(source="topics.count", read_only=True)

    class Meta:
        model = Theme
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "topics_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "topics_count", "created_at", "updated_at"]


class ThemeTopicMapSerializer(serializers.ModelSerializer):  # type: ignore
    """Serializer for ThemeTopicMap."""

    theme_name = serializers.CharField(source="theme.name", read_only=True)
    topic_name = serializers.CharField(source="topic.name", read_only=True)

    class Meta:
        model = ThemeTopicMap
        fields = [
            "id",
            "theme",
            "theme_name",
            "topic",
            "topic_name",
            "weight",
            "created_at",
        ]
        read_only_fields = ["id", "theme_name", "topic_name", "created_at"]
