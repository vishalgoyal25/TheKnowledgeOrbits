"""
Article Generation Engine Admin Interface
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Article, ArticleSourceMap, ArticleGenerationJob


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    """Admin interface for Articles."""
    
    list_display = [
        'title',
        'topic',
        'generation_type',
        'review_status',
        'is_published',
        'word_count',
        'read_time',
        'quality_score',
        'source_count',
        'created_at',
    ]
    
    list_filter = [
        'generation_type',
        'review_status',
        'is_published',
        'topic__subject',
        'created_at',
    ]
    
    search_fields = [
        'title',
        'content',
        'topic__name',
    ]
    
    readonly_fields = [
        'id',
        'slug',
        'word_count',
        'read_time',
        'quality_score',
        'created_at',
        'updated_at',
        'source_count',
        'static_chunks',
        'ca_chunks',
        'content_preview',
    ]
    
    fieldsets = [
        ('Basic Info', {
            'fields': [
                'id',
                'title',
                'slug',
                'topic',
                'generation_type',
            ]
        }),
        ('Content', {
            'fields': [
                'content',
                'summary',
                'content_preview',
            ]
        }),
        ('Metadata', {
            'fields': [
                'word_count',
                'read_time',
                'quality_score',
                'generation_metadata',
            ]
        }),
        ('Review & Publishing', {
            'fields': [
                'review_status',
                'is_published',
                'published_at',
                'published_by',
            ]
        }),
        ('Source Attribution', {
            'fields': [
                'source_count',
                'static_chunks',
                'ca_chunks',
            ]
        }),
        ('Timestamps', {
            'fields': [
                'created_at',
                'updated_at',
            ],
            'classes': ['collapse'],
        }),
    ]
    
    def source_count(self, obj):
        """Total chunks used."""
        return obj.source_chunk_count
    source_count.short_description = 'Sources'
    
    def static_chunks(self, obj):
        """Static chunk count."""
        return obj.static_chunk_count
    static_chunks.short_description = 'Static'
    
    def ca_chunks(self, obj):
        """CA chunk count."""
        return obj.ca_chunk_count
    ca_chunks.short_description = 'CA'
    
    def content_preview(self, obj):
        """First 200 chars of content."""
        if obj.content:
            preview = obj.content[:200]
            return format_html('<div style="max-width:600px;">{}</div>', preview + '...')
        return '-'
    content_preview.short_description = 'Preview'


@admin.register(ArticleSourceMap)
class ArticleSourceMapAdmin(admin.ModelAdmin):
    """Admin interface for Article Source Maps."""
    
    list_display = [
        'article_title',
        'chunk_preview',
        'chunk_source_type',
        'relevance_weight',
        'sequence_order',
        'created_at',
    ]
    
    list_filter = [
        'chunk__source_type',
        'article__topic__subject',
        'created_at',
    ]
    
    search_fields = [
        'article__title',
        'chunk__chunk_text',
    ]
    
    readonly_fields = [
        'id',
        'article',
        'chunk',
        'chunk_preview_full',
        'created_at',
    ]
    
    fieldsets = [
        ('Mapping', {
            'fields': [
                'id',
                'article',
                'chunk',
            ]
        }),
        ('Metadata', {
            'fields': [
                'relevance_weight',
                'sequence_order',
                'chunk_contribution',
            ]
        }),
        ('Chunk Details', {
            'fields': [
                'chunk_preview_full',
            ]
        }),
        ('Timestamps', {
            'fields': [
                'created_at',
            ],
            'classes': ['collapse'],
        }),
    ]
    
    def article_title(self, obj):
        """Article title."""
        return obj.article.title
    article_title.short_description = 'Article'
    
    def chunk_preview(self, obj):
        """Chunk preview."""
        if obj.chunk:
            return obj.chunk.chunk_text[:80] + '...'
        return '-'
    chunk_preview.short_description = 'Chunk'
    
    def chunk_source_type(self, obj):
        """Chunk source type."""
        if obj.chunk:
            return obj.chunk.source_type.upper()
        return '-'
    chunk_source_type.short_description = 'Type'
    
    def chunk_preview_full(self, obj):
        """Full chunk text."""
        if obj.chunk:
            return format_html('<div style="max-width:800px; white-space:pre-wrap;">{}</div>', 
                             obj.chunk.chunk_text)
        return '-'
    chunk_preview_full.short_description = 'Full Chunk Text'


@admin.register(ArticleGenerationJob)
class ArticleGenerationJobAdmin(admin.ModelAdmin):
    """Admin interface for Article Generation Jobs."""
    
    list_display = [
        'topic',
        'status',
        'article_link',
        'requested_by',
        'created_at',
        'completed_at',
        'duration',
    ]
    
    list_filter = [
        'status',
        'topic__subject',
        'created_at',
    ]
    
    search_fields = [
        'topic__name',
        'error_log',
    ]
    
    readonly_fields = [
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
        'duration',
    ]
    
    fieldsets = [
        ('Job Info', {
            'fields': [
                'id',
                'topic',
                'status',
                'requested_by',
            ]
        }),
        ('Result', {
            'fields': [
                'article',
                'error_log',
            ]
        }),
        ('Parameters', {
            'fields': [
                'generation_params',
            ]
        }),
        ('Timing', {
            'fields': [
                'created_at',
                'started_at',
                'completed_at',
                'duration',
            ]
        }),
    ]
    
    def article_link(self, obj):
        """Link to generated article."""
        if obj.article:
            url = reverse('admin:article_generation_article_change', args=[obj.article.id])
            return format_html('<a href="{}">{}</a>', url, obj.article.title)
        return '-'
    article_link.short_description = 'Article'
    
    def duration(self, obj):
        """Job duration."""
        if obj.started_at and obj.completed_at:
            delta = obj.completed_at - obj.started_at
            return f"{delta.total_seconds():.1f}s"
        return '-'
    duration.short_description = 'Duration'

    