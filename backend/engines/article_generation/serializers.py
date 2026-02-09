"""
Article Generation Engine Serializers
"""

from rest_framework import serializers
from .models import Article, ArticleSourceMap, ArticleGenerationJob
from engines.knowledge.serializers import TopicSerializer
from engines.content.serializers import ChunkSerializer


class ArticleSourceMapSerializer(serializers.ModelSerializer):
    """Serializer for ArticleSourceMap with chunk details."""
    
    chunk = ChunkSerializer(read_only=True)
    
    class Meta:
        model = ArticleSourceMap
        fields = [
            'id',
            'chunk',
            'relevance_weight',
            'sequence_order',
            'chunk_contribution',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class ArticleListSerializer(serializers.ModelSerializer):
    """Serializer for article list view."""
    
    topic = TopicSerializer(read_only=True)
    source_chunk_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Article
        fields = [
            'id',
            'title',
            'slug',
            'summary',
            'topic',
            'word_count',
            'read_time',
            'generation_type',
            'quality_score',
            'review_status',
            'is_published',
            'published_at',
            'source_chunk_count',
            'created_at',
        ]
        read_only_fields = fields


class ArticleDetailSerializer(serializers.ModelSerializer):
    """Serializer for article detail view."""
    
    topic = TopicSerializer(read_only=True)
    source_chunks = ArticleSourceMapSerializer(many=True, read_only=True)
    source_chunk_count = serializers.IntegerField(read_only=True)
    static_chunk_count = serializers.IntegerField(read_only=True)
    ca_chunk_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Article
        fields = [
            'id',
            'title',
            'slug',
            'content',
            'summary',
            'topic',
            'word_count',
            'read_time',
            'generation_type',
            'quality_score',
            'review_status',
            'is_published',
            'published_at',
            'published_by',
            'source_chunk_count',
            'static_chunk_count',
            'ca_chunk_count',
            'source_chunks',
            'generation_metadata',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class ArticleGenerationRequestSerializer(serializers.Serializer):
    """Serializer for article generation request."""
    
    topic_id = serializers.UUIDField(required=True)
    include_ca = serializers.BooleanField(default=False)
    
    def validate_topic_id(self, value):
        """Validate that topic exists."""
        from engines.knowledge.models import Topic
        
        if not Topic.objects.filter(id=value).exists():
            raise serializers.ValidationError("Topic not found")
        
        return value


class ArticleGenerationJobSerializer(serializers.ModelSerializer):
    """Serializer for ArticleGenerationJob."""
    
    topic = TopicSerializer(read_only=True)
    article = ArticleListSerializer(read_only=True)
    
    class Meta:
        model = ArticleGenerationJob
        fields = [
            'id',
            'topic',
            'article',
            'status',
            'error_log',
            'requested_by',
            'generation_params',
            'started_at',
            'completed_at',
            'created_at',
        ]
        read_only_fields = fields
        