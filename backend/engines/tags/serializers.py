"""
engines/tags/serializers.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase L1 — Tags Engine serializers.

Serializers:
  TagSerializer            — list fields (id, name, slug, type, usage_count)
  TagDetailSerializer      — all fields + recent_articles (last 5 daily CA)
  ConceptPageSerializer    — list fields (id, name, slug, brief_description, is_content_ready)
  ConceptPageDetailSerializer — all fields + body (if ready) + linked_articles (last 5)
"""

from rest_framework import serializers

from engines.tags.models import ConceptPage, Tag


# ── Tag ───────────────────────────────────────────────────────────────────────


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug", "description", "tag_type", "usage_count"]


class TagDetailSerializer(serializers.ModelSerializer):
    recent_articles = serializers.SerializerMethodField()

    class Meta:
        model = Tag
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "tag_type",
            "usage_count",
            "is_active",
            "created_at",
            "recent_articles",
        ]

    def get_recent_articles(self, obj):
        from engines.daily_ca.models import DailyCaArticle

        article_tags = obj.article_tags.filter(content_type="daily_ca").order_by(
            "-created_at"
        )[:5]
        ids = [at.object_id for at in article_tags]
        articles = DailyCaArticle.objects.filter(id__in=ids, is_published=True)
        return [{"title": a.title, "slug": a.slug} for a in articles]


# ── ConceptPage ───────────────────────────────────────────────────────────────


class ConceptPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConceptPage
        fields = [
            "id",
            "name",
            "slug",
            "brief_description",
            "is_content_ready",
            "usage_count",
        ]


class ConceptPageDetailSerializer(serializers.ModelSerializer):
    body = serializers.SerializerMethodField()
    linked_articles = serializers.SerializerMethodField()

    class Meta:
        model = ConceptPage
        fields = [
            "id",
            "name",
            "slug",
            "brief_description",
            "body",
            "is_content_ready",
            "usage_count",
            "created_at",
            "linked_articles",
        ]

    def get_body(self, obj):
        """Return body_md only when full content is ready."""
        return obj.body_md if obj.is_content_ready else None

    def get_linked_articles(self, obj):
        from engines.daily_ca.models import DailyCaArticle

        links = obj.article_links.order_by("-created_at")[:5]
        ids = [link.daily_ca_article_id for link in links]
        articles = DailyCaArticle.objects.filter(id__in=ids, is_published=True)
        return [{"title": a.title, "slug": a.slug} for a in articles]
