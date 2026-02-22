"""
Current Affairs Engine - Admin Interface
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import CASource, CAArticle, CAChunk, CATopicLink


@admin.register(CASource)
class CASourceAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "source_type",
        "is_active",
        "article_count",
        "last_scraped_at",
        "status_indicator",
    ]
    list_filter = ["is_active", "source_type", "scrape_frequency"]
    search_fields = ["name", "url"]
    readonly_fields = [
        "id",
        "article_count",
        "last_scraped_at",
        "last_error",
        "created_at",
        "updated_at",
    ]

    fieldsets = [
        ("Basic Information", {"fields": ["id", "name", "source_type", "url"]}),
        ("Scraping Configuration", {"fields": ["is_active", "scrape_frequency"]}),
        ("Statistics", {"fields": ["article_count", "last_scraped_at", "last_error"]}),
        (
            "Timestamps",
            {"fields": ["created_at", "updated_at"], "classes": ["collapse"]},
        ),
    ]

    def status_indicator(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">●</span> Active')
        return format_html('<span style="color: red;">●</span> Inactive')

    status_indicator.short_description = "Status"


@admin.register(CAArticle)
class CAArticleAdmin(admin.ModelAdmin):
    list_display = [
        "title_short",
        "source",
        "published_at",
        "processing_status",
        "chunk_count",
        "word_count",
    ]
    list_filter = ["processing_status", "source", "published_at"]
    search_fields = ["title", "content", "url"]
    readonly_fields = [
        "id",
        "word_count",
        "chunk_count",
        "processed_at",
        "created_at",
        "updated_at",
    ]
    date_hierarchy = "published_at"

    fieldsets = [
        (
            "Article Information",
            {"fields": ["id", "source", "title", "url", "author", "published_at"]},
        ),
        ("Content", {"fields": ["content", "summary", "categories"]}),
        (
            "Processing",
            {
                "fields": [
                    "processing_status",
                    "processing_error",
                    "processed_at",
                    "word_count",
                    "chunk_count",
                ]
            },
        ),
        (
            "Timestamps",
            {"fields": ["created_at", "updated_at"], "classes": ["collapse"]},
        ),
    ]

    def title_short(self, obj):
        return obj.title[:60] + ("..." if len(obj.title) > 60 else "")

    title_short.short_description = "Title"

    actions = ["process_articles"]

    def process_articles(self, request, queryset):
        from .services.ca_processor import CAProcessorService

        processed = 0
        for article in queryset.filter(processing_status="pending"):
            if CAProcessorService.process_article(article):
                processed += 1
        self.message_user(request, f"Processed {processed} articles")

    process_articles.short_description = "Process selected articles"


@admin.register(CAChunk)
class CAChunkAdmin(admin.ModelAdmin):
    list_display = [
        "id_short",
        "article_title",
        "chunk_index",
        "published_at",
        "is_expired",
        "topic_count",
        "quality_flag",
    ]
    list_filter = ["is_expired", "quality_flag", "published_at"]
    search_fields = ["chunk_text", "ca_article__title"]
    readonly_fields = ["id", "embedding_id", "created_at", "updated_at"]
    date_hierarchy = "published_at"

    fieldsets = [
        (
            "Chunk Information",
            {"fields": ["id", "ca_article", "chunk_index", "chunk_text"]},
        ),
        (
            "Source & Time",
            {"fields": ["source_type", "published_at", "expiry_date", "is_expired"]},
        ),
        ("Quality", {"fields": ["quality_flag", "confidence_score"]}),
        ("Embedding", {"fields": ["embedding_id"]}),
        (
            "Timestamps",
            {"fields": ["created_at", "updated_at"], "classes": ["collapse"]},
        ),
    ]

    def id_short(self, obj):
        return str(obj.id)[:8]

    id_short.short_description = "ID"

    def article_title(self, obj):
        return obj.ca_article.title[:50] + (
            "..." if len(obj.ca_article.title) > 50 else ""
        )

    article_title.short_description = "Article"

    def topic_count(self, obj):
        return obj.topic_links.count()

    topic_count.short_description = "Topics"


@admin.register(CATopicLink)
class CATopicLinkAdmin(admin.ModelAdmin):
    list_display = [
        "id_short",
        "ca_article_title",
        "topic",
        "relevance_score",
        "link_method",
    ]
    list_filter = ["link_method", "relevance_score"]
    search_fields = ["ca_chunk__ca_article__title", "topic__name"]
    readonly_fields = ["id", "created_at", "updated_at"]

    fieldsets = [
        ("Link Information", {"fields": ["id", "ca_chunk", "topic"]}),
        ("Relevance", {"fields": ["relevance_score", "link_method"]}),
        (
            "Timestamps",
            {"fields": ["created_at", "updated_at"], "classes": ["collapse"]},
        ),
    ]

    def id_short(self, obj):
        return str(obj.id)[:8]

    id_short.short_description = "ID"

    def ca_article_title(self, obj):
        return obj.ca_chunk.ca_article.title[:40]

    ca_article_title.short_description = "CA Article"
