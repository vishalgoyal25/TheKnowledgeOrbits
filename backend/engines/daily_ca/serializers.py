"""
engines/daily_ca/serializers.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase L2 — Daily CA Engine serializers.

Serializers:
  DailyCaArticleListSerializer   — card/list view (no body_md)
  DailyCaArticleDetailSerializer — full detail + concept_links + related + static_background
  DailyCaProposalSerializer      — admin proposal review
  StaticBackgroundSerializer     — nested BookContent summary (used in detail)
"""

from rest_framework import serializers

from engines.daily_ca.models import CaDailyProposal, DailyCaArticle


# ── Nested: Static Background (BookContent summary) ──────────────────────────


class StaticBackgroundSerializer(serializers.Serializer):
    """Minimal read-only serializer for BookContent — nested in article detail."""

    id = serializers.UUIDField()
    topic_name = serializers.SerializerMethodField()
    subject_name = serializers.SerializerMethodField()
    word_count = serializers.IntegerField()
    quality_score = serializers.FloatField()
    is_published = serializers.BooleanField()

    def get_topic_name(self, obj):
        try:
            return obj.topic.name
        except Exception:
            return None

    def get_subject_name(self, obj):
        try:
            return obj.subject.name
        except Exception:
            return None


# ── DailyCaArticle: List ──────────────────────────────────────────────────────


class DailyCaArticleListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for article cards/lists.
    Does NOT include body_md — keeps response small.
    """

    tags = serializers.SerializerMethodField()
    topic_name = serializers.SerializerMethodField()

    class Meta:
        model = DailyCaArticle
        fields = [
            "id",
            "slug",
            "title",
            "subject_name",
            "gs_paper",
            "published_date",
            "news_context",
            "hero_image_url",
            "quality_score",
            "order_on_date",
            "topic_name",
            "tags",
        ]

    def get_tags(self, obj):
        from engines.tags.models import ArticleTag
        from engines.tags.serializers import TagSerializer

        article_tags = (
            ArticleTag.objects.filter(content_type="daily_ca", object_id=obj.id)
            .select_related("tag")
            .order_by("-relevance")
        )
        return TagSerializer([at.tag for at in article_tags], many=True).data

    def get_topic_name(self, obj):
        try:
            return obj.topic.name if obj.topic else None
        except Exception:
            return None


# ── DailyCaArticle: Detail ────────────────────────────────────────────────────


class DailyCaArticleDetailSerializer(serializers.ModelSerializer):
    """
    Full detail serializer — used at /api/v1/daily-ca/article/<slug>/.
    Includes body_md_processed, static_background, concept_links, related_articles.
    """

    tags = serializers.SerializerMethodField()
    topic_name = serializers.SerializerMethodField()
    concept_links = serializers.SerializerMethodField()
    static_background = serializers.SerializerMethodField()
    related_articles = serializers.SerializerMethodField()

    class Meta:
        model = DailyCaArticle
        fields = [
            "id",
            "slug",
            "title",
            "subject_name",
            "gs_paper",
            "published_date",
            "news_context",
            "hero_image_url",
            "body_md_processed",
            "sources_used",
            "quality_score",
            "order_on_date",
            "is_published",
            "generation_metadata",
            "created_at",
            "topic_name",
            "tags",
            "concept_links",
            "static_background",
            "related_articles",
        ]

    def get_tags(self, obj):
        from engines.tags.models import ArticleTag
        from engines.tags.serializers import TagSerializer

        article_tags = (
            ArticleTag.objects.filter(content_type="daily_ca", object_id=obj.id)
            .select_related("tag")
            .order_by("-relevance")
        )
        return TagSerializer([at.tag for at in article_tags], many=True).data

    def get_topic_name(self, obj):
        try:
            return obj.topic.name if obj.topic else None
        except Exception:
            return None

    def get_concept_links(self, obj):
        from engines.tags.models import ConceptArticleLink
        from engines.tags.serializers import ConceptPageSerializer

        links = (
            ConceptArticleLink.objects.filter(daily_ca_article_id=obj.id)
            .select_related("concept_page")
            .order_by("-created_at")
        )
        return ConceptPageSerializer(
            [link.concept_page for link in links], many=True
        ).data

    def get_static_background(self, obj):
        if obj.static_background:
            return StaticBackgroundSerializer(obj.static_background).data
        return None

    def get_related_articles(self, obj):
        """5 recent published articles from the same subject (excluding self)."""
        qs = (
            DailyCaArticle.objects.filter(
                subject_name=obj.subject_name, is_published=True
            )
            .exclude(id=obj.id)
            .order_by("-published_date")[:5]
        )
        return DailyCaArticleListSerializer(qs, many=True).data


# ── CaDailyProposal ───────────────────────────────────────────────────────────


class DailyCaProposalSerializer(serializers.ModelSerializer):
    topic_name = serializers.SerializerMethodField()
    source_count = serializers.SerializerMethodField()

    class Meta:
        model = CaDailyProposal
        fields = [
            "id",
            "title",
            "description",
            "topic_name",
            "subject_name",
            "gs_paper",
            "relevance_score",
            "source_count",
            "status",
            "approved_at",
            "date",
        ]

    def get_topic_name(self, obj):
        try:
            return obj.topic.name if obj.topic else None
        except Exception:
            return None

    def get_source_count(self, obj):
        return len(obj.source_urls) if obj.source_urls else 0
