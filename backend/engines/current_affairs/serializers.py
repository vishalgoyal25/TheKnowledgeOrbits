"""
Current Affairs Engine - Serializers
"""

from typing import Any

from rest_framework import serializers

from engines.knowledge.serializers import TopicSerializer

from .models import CAArticle, CAChunk, CASource, CATopicLink


class CASourceSerializer(serializers.ModelSerializer):  # type: ignore
    class Meta:
        model = CASource
        fields = [
            "id",
            "name",
            "source_type",
            "url",
            "is_active",
            "scrape_frequency",
            "last_scraped_at",
            "article_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "last_scraped_at",
            "article_count",
            "created_at",
            "updated_at",
        ]


class CAArticleSerializer(serializers.ModelSerializer):  # type: ignore
    source_name = serializers.CharField(source="source.name", read_only=True)

    class Meta:
        model = CAArticle
        fields = [
            "id",
            "source",
            "source_name",
            "title",
            "url",
            "content",
            "summary",
            "published_at",
            "author",
            "categories",
            "processing_status",
            "word_count",
            "chunk_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "source_name",
            "processing_status",
            "word_count",
            "chunk_count",
            "created_at",
            "updated_at",
        ]


class CAChunkSerializer(serializers.ModelSerializer):  # type: ignore
    article_title = serializers.CharField(source="ca_article.title", read_only=True)
    topic_count = serializers.SerializerMethodField()

    class Meta:
        model = CAChunk
        fields = [
            "id",
            "ca_article",
            "article_title",
            "chunk_text",
            "chunk_index",
            "source_type",
            "published_at",
            "expiry_date",
            "is_expired",
            "quality_flag",
            "confidence_score",
            "topic_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "article_title",
            "source_type",
            "expiry_date",
            "topic_count",
            "created_at",
            "updated_at",
        ]

    def get_topic_count(self, obj) -> Any:  # type: ignore
        return obj.topic_links.count()


class CATopicLinkSerializer(serializers.ModelSerializer):  # type: ignore
    topic = TopicSerializer(read_only=True)
    chunk_text = serializers.CharField(source="ca_chunk.chunk_text", read_only=True)
    article_title = serializers.CharField(
        source="ca_chunk.ca_article.title", read_only=True
    )

    class Meta:
        model = CATopicLink
        fields = [
            "id",
            "ca_chunk",
            "topic",
            "chunk_text",
            "article_title",
            "relevance_score",
            "link_method",
            "created_at",
        ]
        read_only_fields = ["id", "chunk_text", "article_title", "created_at"]
