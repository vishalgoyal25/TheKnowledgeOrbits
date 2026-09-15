"""
engines/tags/views.py
━━━━━━━━━━━━━━━━━━━━━
Phase L1 — Tags Engine API views.

Routes served:
  /api/v1/tags/                   → TagListView
  /api/v1/tags/<slug>/            → TagDetailView
  /api/v1/tags/<slug>/articles/   → TagArticlesView

  /api/v1/concepts/               → ConceptListView
  /api/v1/concepts/sitemap/       → ConceptSitemapView   (G3.3, curated subset)
  /api/v1/concepts/<slug>/        → ConceptDetailView

All views: read-only, no authentication required.
"""

from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from engines.tags.models import ArticleTag, ConceptPage, Tag
from engines.tags.serializers import (
    ConceptPageDetailSerializer,
    ConceptPageSerializer,
    TagDetailSerializer,
    TagSerializer,
)
from engines.tags.services.concept_seo_service import is_indexable


# ── Tag Views ─────────────────────────────────────────────────────────────────


class TagListView(generics.ListAPIView):
    """
    GET /api/v1/tags/
    List all active tags, paginated. Optional filter: ?type=scheme
    """

    serializer_class = TagSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = Tag.objects.filter(is_active=True)
        tag_type = self.request.query_params.get("type")
        if tag_type:
            qs = qs.filter(tag_type=tag_type)
        return qs


class TagDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/tags/<slug>/
    Tag detail + list of recent CA articles using this tag (last 5).
    """

    serializer_class = TagDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"
    queryset = Tag.objects.filter(is_active=True)


class TagArticlesView(APIView):
    """
    GET /api/v1/tags/<slug>/articles/
    All published DailyCaArticles carrying this tag, newest first.
    Supports ?limit=20&offset=0 pagination.
    """

    permission_classes = [AllowAny]

    def get(self, request, slug):
        from engines.daily_ca.models import DailyCaArticle
        from engines.daily_ca.serializers import DailyCaArticleListSerializer

        tag = get_object_or_404(Tag, slug=slug, is_active=True)
        limit = int(request.query_params.get("limit", 20))
        offset = int(request.query_params.get("offset", 0))

        # P1.7 — count via DB aggregate, not by materialising all rows into a Python list
        article_tags = ArticleTag.objects.filter(tag=tag, content_type="daily_ca")
        total = article_tags.count()

        tag_ids = article_tags.values_list("object_id", flat=True)
        articles = DailyCaArticle.objects.filter(
            id__in=tag_ids, is_published=True
        ).order_by("-published_date")[offset : offset + limit]
        serializer = DailyCaArticleListSerializer(articles, many=True)
        return Response(
            {
                "tag": tag.name,
                "total": total,
                "limit": limit,
                "offset": offset,
                "results": serializer.data,
            }
        )


# ── Concept Views ─────────────────────────────────────────────────────────────


class ConceptListView(generics.ListAPIView):
    """
    GET /api/v1/concepts/
    List all concept pages, paginated. Optional filter: ?is_content_ready=true
    """

    serializer_class = ConceptPageSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = ConceptPage.objects.all()
        ready = self.request.query_params.get("is_content_ready")
        if ready is not None:
            qs = qs.filter(is_content_ready=ready.lower() == "true")
        return qs


class ConceptDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/concepts/<slug>/
    Concept detail. Returns brief_description always.
    Returns body (full markdown) only when is_content_ready=True.
    """

    serializer_class = ConceptPageDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"
    queryset = ConceptPage.objects.all()


class ConceptSitemapView(APIView):
    """
    GET /api/v1/concepts/sitemap/  (G3.3)

    slug + last-modified for every concept page that passes the G0.3
    indexability rule (concept_seo_service.is_indexable) — the curated subset,
    never all 2,438. Scans body text, so it is cached for an hour; the rule is
    live, so today's new pages classify themselves tomorrow.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        cache_key = "sitemap_entries_concepts_v1"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        payload = [
            {"slug": c.slug, "lastmod": c.updated_at.isoformat()}
            for c in ConceptPage.objects.filter(is_content_ready=True)
            .only("slug", "body_md", "is_content_ready", "updated_at")
            .iterator(chunk_size=200)
            if is_indexable(c)
        ]
        cache.set(cache_key, payload, timeout=3600)
        return Response(payload)
