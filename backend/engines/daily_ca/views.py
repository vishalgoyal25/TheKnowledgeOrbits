"""
engines/daily_ca/views.py
━━━━━━━━━━━━━━━━━━━━━━━━━
Phase L2 + L3 — Daily CA Engine API views.

Public endpoints (L2):
  GET /api/v1/daily-ca/today/             → today's published articles (Redis-cached 5min)
  GET /api/v1/daily-ca/<date>/            → articles for specific date (YYYY-MM-DD)
  GET /api/v1/daily-ca/article/<slug>/    → full article detail
  GET /api/v1/daily-ca/archive/           → last 30 days, date-grouped summary

Admin endpoints — no auth (L3 — solo developer):
  GET  /api/v1/admin/daily-ca/proposals/<date>/     → list proposals for review
  POST /api/v1/admin/daily-ca/proposals/approve/    → approve selected IDs (max 10)
  GET  /api/v1/admin/daily-ca/generate/status/      → proposal status summary for a date
  POST /api/v1/admin/daily-ca/publish/<date>/       → publish all generated articles for date
  GET  /api/v1/admin/daily-ca/articles/<date>/      → list all articles for date (incl. unpublished)
"""

import threading
from datetime import datetime, timedelta

import sentry_sdk
import structlog
from django.core.cache import cache
from django.core.management import call_command
from django.db.models import Count
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from engines.daily_ca.models import CaDailyProposal, DailyCaArticle
from engines.daily_ca.serializers import (
    DailyCaArticleDetailSerializer,
    DailyCaArticleListSerializer,
    DailyCaProposalSerializer,
)

logger = structlog.get_logger(__name__)

_TODAY_CACHE_TTL = 300  # 5 minutes  — today's articles change once/day
_DATE_CACHE_TTL = 3600  # 60 minutes — past-date articles are immutable
_ARCHIVE_CACHE_TTL = 300  # 5 minutes  — archive changes when new articles publish


def _build_tags_map(articles: list) -> dict:
    """
    P2.1 — Bulk-fetch all ArticleTags for a list of DailyCaArticle objects
    in a single query and return a dict keyed by article UUID string.

    Without this: ArchiveView fires 1 ArticleTag query per article = 300 queries.
    With this: 1 query total, regardless of article count.

    Usage:
        articles_list = list(qs)
        tags_map = _build_tags_map(articles_list)
        DailyCaArticleListSerializer(articles_list, many=True,
                                     context={"prefetched_tags": tags_map})
    """
    from engines.tags.models import ArticleTag

    if not articles:
        return {}

    ids = [a.id for a in articles]
    article_tags = (
        ArticleTag.objects.filter(content_type="daily_ca", object_id__in=ids)
        .select_related("tag")
        .order_by("-relevance")
    )
    tags_map: dict = {}
    for at in article_tags:
        tags_map.setdefault(str(at.object_id), []).append(at.tag)
    return tags_map


# ── Public Views ──────────────────────────────────────────────────────────────


class TodayView(APIView):
    """
    GET /api/v1/daily-ca/today/
    Returns today's published articles, ordered by order_on_date.
    Response is Redis-cached for 5 minutes.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        today = timezone.now().date()
        category = request.query_params.get("category", "").strip().lower()

        # Cache is skipped when category filter is applied (filtered result not cached)
        if not category:
            cache_key = f"daily_ca_today_{today}"
            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached)

        articles = (
            DailyCaArticle.objects.filter(published_date=today, is_published=True)
            .defer(
                "body_md",
                "body_md_processed",
                "generation_metadata",
                "ca_chunk_ids",
                "static_links",
            )
            .order_by("order_on_date")
        )

        if category:
            articles = articles.filter(news_category=category)

        # P2.1 — evaluate queryset once, bulk-fetch tags in 1 query
        articles_list = list(articles)
        tags_map = _build_tags_map(articles_list)
        data = DailyCaArticleListSerializer(
            articles_list, many=True, context={"prefetched_tags": tags_map}
        ).data
        payload = {"date": str(today), "count": len(data), "articles": data}

        if not category:
            cache.set(cache_key, payload, timeout=_TODAY_CACHE_TTL)

        logger.info(
            "today_view_cache_miss",
            date=str(today),
            count=len(data),
            category=category or None,
        )
        return Response(payload)


class DateView(APIView):
    """
    GET /api/v1/daily-ca/<date>/
    Returns published articles for a specific date (format: YYYY-MM-DD).
    """

    permission_classes = [AllowAny]

    def get(self, request, date_str):
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."}, status=400
            )

        category = request.query_params.get("category", "").strip().lower()

        # Cache per date+category — past dates are immutable (60-min TTL)
        if not category:
            cache_key = f"daily_ca_date_{date_str}_v1"
            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached)

        articles = (
            DailyCaArticle.objects.filter(published_date=target_date, is_published=True)
            .defer(
                "body_md",
                "body_md_processed",
                "generation_metadata",
                "ca_chunk_ids",
                "static_links",
            )
            .order_by("order_on_date")
        )

        if category:
            articles = articles.filter(news_category=category)

        # P2.1 — evaluate queryset once, bulk-fetch tags in 1 query
        articles_list = list(articles)
        tags_map = _build_tags_map(articles_list)
        data = DailyCaArticleListSerializer(
            articles_list, many=True, context={"prefetched_tags": tags_map}
        ).data
        payload = {"date": date_str, "count": len(data), "articles": data}

        if not category:
            cache.set(cache_key, payload, timeout=_DATE_CACHE_TTL)

        return Response(payload)


class ArticleDetailView(APIView):
    """
    GET /api/v1/daily-ca/article/<slug>/
    Full article detail with tags, concept_links, static_background, related_articles.
    """

    permission_classes = [AllowAny]

    def get(self, request, slug):
        try:
            article = DailyCaArticle.objects.select_related(
                "topic", "static_background"
            ).get(slug=slug, is_published=True)
        except DailyCaArticle.DoesNotExist:
            return Response({"error": "Article not found."}, status=404)

        data = DailyCaArticleDetailSerializer(article).data
        return Response(data)


class ArchiveView(APIView):
    """
    GET /api/v1/daily-ca/archive/
    Date-grouped archive with cursor pagination.

    Query params:
      ?days=10     — number of calendar days to return (default: 10, max: 30)
      ?before=YYYY-MM-DD — return days strictly before this date (cursor for "load more")

    Response shape:
      { days: int, has_more: bool, archive: [{date, count, articles[]}] }

    P2.6 — replaces the old 30-day single-shot response (300 articles at once)
    with a paginated response. Frontend requests 10 days at a time; "Load more"
    passes ?before=<oldest_date_in_current_result> to fetch the next page.
    """

    permission_classes = [AllowAny]

    _MAX_DAYS = 30
    _DEFAULT_DAYS = 10

    def get(self, request):
        # ── Parse query params ────────────────────────────────────────────────
        try:
            days_limit = min(
                int(request.query_params.get("days", self._DEFAULT_DAYS)),
                self._MAX_DAYS,
            )
        except (ValueError, TypeError):
            days_limit = self._DEFAULT_DAYS

        before_str = request.query_params.get("before", "").strip()
        if before_str:
            try:
                before_date = datetime.strptime(before_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Invalid before date format. Use YYYY-MM-DD."}, status=400
                )
            end_date = before_date - timedelta(days=1)
        else:
            end_date = timezone.now().date()

        cutoff = end_date - timedelta(days=days_limit)

        # ── Cache (keyed by days + cursor) ────────────────────────────────────
        cache_key = f"daily_ca_archive_{days_limit}_{before_str}_v1"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        # ── Fetch & group ─────────────────────────────────────────────────────
        articles = (
            DailyCaArticle.objects.filter(
                published_date__gt=cutoff,
                published_date__lte=end_date,
                is_published=True,
            )
            .defer(
                "body_md",
                "body_md_processed",
                "generation_metadata",
                "ca_chunk_ids",
                "static_links",
            )
            .order_by("-published_date", "order_on_date")
        )

        # P2.1 — evaluate once, bulk-fetch all tags in 1 query, then group
        articles_list = list(articles)
        tags_map = _build_tags_map(articles_list)
        serializer_context = {"prefetched_tags": tags_map}

        grouped: dict = {}
        for article in articles_list:
            d = str(article.published_date)
            grouped.setdefault(d, []).append(
                DailyCaArticleListSerializer(article, context=serializer_context).data
            )

        result = [
            {"date": d, "count": len(items), "articles": items}
            for d, items in sorted(grouped.items(), reverse=True)
        ]

        # ── has_more: any published articles exist before the fetched window ──
        has_more = DailyCaArticle.objects.filter(
            published_date__lte=cutoff, is_published=True
        ).exists()

        payload = {"days": len(result), "has_more": has_more, "archive": result}
        cache.set(cache_key, payload, timeout=_ARCHIVE_CACHE_TTL)
        return Response(payload)


# ── Admin Views (no auth — solo developer) ────────────────────────────────────


class AdminProposalListView(APIView):
    """
    GET /api/v1/admin/daily-ca/proposals/<date>/
    List all proposals for a given date, ordered by relevance_score DESC.
    """

    permission_classes = [AllowAny]

    def get(self, request, date_str):
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."}, status=400
            )

        proposals = (
            CaDailyProposal.objects.filter(date=target_date)
            .select_related("topic")
            .order_by("-relevance_score")
        )
        data = DailyCaProposalSerializer(proposals, many=True).data
        return Response({"date": date_str, "count": len(data), "proposals": data})


class AdminApproveView(APIView):
    """
    POST /api/v1/admin/daily-ca/proposals/approve/
    Approve selected proposal IDs (max 10). Sets status='approved', approved_at=now().
    Body: {"proposal_ids": ["uuid1", "uuid2", ...]}
    """

    permission_classes = [AllowAny]

    def post(self, request):
        proposal_ids = request.data.get("proposal_ids", [])
        if not proposal_ids:
            return Response({"error": "proposal_ids is required."}, status=400)
        if len(proposal_ids) > 10:
            return Response(
                {
                    "error": f"Max 10 proposals per approval batch. Got {len(proposal_ids)}."
                },
                status=400,
            )

        try:
            now = timezone.now()
            updated = CaDailyProposal.objects.filter(
                id__in=proposal_ids, status__in=["pending", "failed"]
            ).update(status="approved", approved_at=now)
            logger.info("admin_approve", count=updated, ids=proposal_ids)
            return Response({"approved": updated, "requested": len(proposal_ids)})

        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error("admin_approve_failed", error=str(exc))
            return Response({"error": str(exc)}, status=500)


class AdminGenerateStatusView(APIView):
    """
    GET /api/v1/admin/daily-ca/generate/status/?date=YYYY-MM-DD
    Returns proposal status breakdown for a date (default: today).
    Useful for monitoring progress mid-generation.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        date_str = request.query_params.get("date")
        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use YYYY-MM-DD."}, status=400
                )
        else:
            target_date = timezone.now().date()

        # P1.6 — single aggregate query replaces loop + .count() double-hit
        status_data = (
            CaDailyProposal.objects.filter(date=target_date)
            .values("status")
            .annotate(count=Count("id"))
        )
        status_counts: dict = {item["status"]: item["count"] for item in status_data}
        total = sum(status_counts.values())
        generated = status_counts.get("generated", 0)

        return Response(
            {
                "date": str(target_date),
                "total": total,
                "status_breakdown": status_counts,
                "generation_complete": generated == total and total > 0,
                "articles_generated": generated,
            }
        )


class AdminPublishDateView(APIView):
    """
    POST /api/v1/admin/daily-ca/publish/<date>/
    Publishes all generated (is_published=False) articles for a date.
    Sets is_published=True on all matching articles.
    """

    permission_classes = [AllowAny]

    def post(self, request, date_str):
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."}, status=400
            )

        try:
            updated = DailyCaArticle.objects.filter(
                published_date=target_date, is_published=False
            ).update(is_published=True)

            # Bust today + archive + date caches on any publish
            cache.delete(f"daily_ca_today_{target_date}")
            cache.delete(f"daily_ca_date_{date_str}_v1")
            cache.delete("daily_ca_archive_v1")  # legacy key (backward compat)
            cache.delete("daily_ca_archive_10__v1")  # P2.6 default paginated key

            logger.info("admin_publish_date", date=date_str, published=updated)
            return Response({"date": date_str, "published": updated})

        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error("admin_publish_failed", error=str(exc))
            return Response({"error": str(exc)}, status=500)


class AdminGenerateRunView(APIView):
    """
    POST /api/v1/admin/daily-ca/generate/run/
    Triggers generate_daily_ca management command in a background daemon thread.
    Returns 202 immediately — generation runs asynchronously.

    Body:
        {
            "date": "YYYY-MM-DD",   (optional; defaults to today)
            "auto_publish": true    (optional; default true — H2)
        }

    Phase H2: auto_publish param forwarded to --auto-publish flag.
    Default is True so "Approve & Generate" from the frontend publishes
    articles automatically after generation completes.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        date_str = request.data.get("date") or str(timezone.now().date())
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."}, status=400
            )

        # H2: read auto_publish from request body — default True so the
        # frontend "Approve & Generate" flow publishes without extra steps.
        auto_publish: bool = bool(request.data.get("auto_publish", True))

        def _run():
            try:
                args = [f"--date={date_str}"]
                if auto_publish:
                    args.append("--auto-publish")
                call_command("generate_daily_ca", *args)
            except Exception as exc:
                sentry_sdk.capture_exception(exc)
                logger.error(
                    "admin_generate_run_failed",
                    date=date_str,
                    auto_publish=auto_publish,
                    error=str(exc),
                )

        t = threading.Thread(target=_run, daemon=True)
        t.start()

        logger.info(
            "admin_generate_run_triggered",
            date=date_str,
            auto_publish=auto_publish,
        )
        return Response(
            {"status": "triggered", "date": date_str, "auto_publish": auto_publish},
            status=202,
        )


class AdminArticlesDateView(APIView):
    """
    GET /api/v1/admin/daily-ca/articles/<date>/
    List ALL articles for a date — including unpublished (for admin review).
    Returns full detail including quality_score and generation_metadata.
    """

    permission_classes = [AllowAny]

    def get(self, request, date_str):
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."}, status=400
            )

        articles = (
            DailyCaArticle.objects.filter(published_date=target_date)
            .select_related("topic", "static_background")
            .order_by("order_on_date", "-quality_score")
        )
        data = DailyCaArticleDetailSerializer(articles, many=True).data
        return Response({"date": date_str, "count": len(data), "articles": data})
