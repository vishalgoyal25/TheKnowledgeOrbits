"""
Knowledge Engine Serializers
"""
from rest_framework import serializers
from engines.knowledge.models import (
    Program,
    Subject,
    Module,
    Topic,
    ChunkTopicMap,
    Theme,
    ThemeTopicMap
)


class ProgramSerializer(serializers.ModelSerializer):
    """Serializer for Program."""
    
    subjects_count = serializers.IntegerField(
        source='subjects.count',
        read_only=True
    )
    
    class Meta:
        model = Program
        fields = [
            'id',
            'name',
            'description',
            'exam_pattern',
            'is_active',
            'subjects_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'subjects_count', 'created_at', 'updated_at']


class SubjectSerializer(serializers.ModelSerializer):
    """Serializer for Subject."""
    
    program_name = serializers.CharField(
        source='program.name',
        read_only=True
    )
    modules_count = serializers.IntegerField(
        source='modules.count',
        read_only=True
    )
    
    class Meta:
        model = Subject
        fields = [
            'id',
            'name',
            'program',
            'program_name',
            'description',
            'order_index',
            'is_active',
            'modules_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'program_name', 'modules_count', 'created_at', 'updated_at']


class ModuleSerializer(serializers.ModelSerializer):
    """Serializer for Module."""
    
    subject_name = serializers.CharField(
        source='subject.name',
        read_only=True
    )
    topics_count = serializers.IntegerField(
        source='topics.count',
        read_only=True
    )
    
    class Meta:
        model = Module
        fields = [
            'id',
            'name',
            'subject',
            'subject_name',
            'description',
            'order_index',
            'is_active',
            'topics_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'subject_name', 'topics_count', 'created_at', 'updated_at']


class TopicSerializer(serializers.ModelSerializer):
    """Serializer for Topic."""
    
    module_name = serializers.CharField(
        source='module.name',
        read_only=True
    )
    subject_name = serializers.CharField(
        source='subject.name',
        read_only=True
    )
    chunks_count = serializers.IntegerField(
        source='chunk_mappings.count',
        read_only=True
    )
    
    class Meta:
        model = Topic
        fields = [
            'id',
            'name',
            'module',
            'module_name',
            'subject',
            'subject_name',
            'parent_topic',
            'description',
            'keywords',
            'topic_type',
            'difficulty_level',
            'order_index',
            'is_active',
            'chunks_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'module_name', 'subject_name', 'chunks_count', 'created_at', 'updated_at']


class ChunkTopicMapSerializer(serializers.ModelSerializer):
    """Serializer for ChunkTopicMap."""
    
    topic_name = serializers.CharField(
        source='topic.name',
        read_only=True
    )
    chunk_text_preview = serializers.SerializerMethodField()
    
    def get_chunk_text_preview(self, obj):
        """Get chunk text preview (first 200 chars)."""
        text = obj.chunk.chunk_text
        return text[:200] + '...' if len(text) > 200 else text
    
    class Meta:
        model = ChunkTopicMap
        fields = [
            'id',
            'chunk',
            'chunk_text_preview',
            'topic',
            'topic_name',
            'relevance_score',
            'priority',
            'auto_mapped',
            'approved_by',
            'created_at'
        ]
        read_only_fields = ['id', 'topic_name', 'chunk_text_preview', 'created_at']


class ThemeSerializer(serializers.ModelSerializer):
    """Serializer for Theme."""
    
    topics_count = serializers.IntegerField(
        source='topics.count',
        read_only=True
    )
    
    class Meta:
        model = Theme
        fields = [
            'id',
            'name',
            'description',
            'is_active',
            'topics_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'topics_count', 'created_at', 'updated_at']


class ThemeTopicMapSerializer(serializers.ModelSerializer):
    """Serializer for ThemeTopicMap."""
    
    theme_name = serializers.CharField(
        source='theme.name',
        read_only=True
    )
    topic_name = serializers.CharField(
        source='topic.name',
        read_only=True
    )
    
    class Meta:
        model = ThemeTopicMap
        fields = [
            'id',
            'theme',
            'theme_name',
            'topic',
            'topic_name',
            'weight',
            'created_at'
        ]
        read_only_fields = ['id', 'theme_name', 'topic_name', 'created_at']
        