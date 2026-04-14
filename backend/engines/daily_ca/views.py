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

_TODAY_CACHE_TTL = 300  # 5 minutes


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

        articles = DailyCaArticle.objects.filter(
            published_date=today, is_published=True
        ).order_by("order_on_date")

        if category:
            articles = articles.filter(news_category=category)

        data = DailyCaArticleListSerializer(articles, many=True).data
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

        articles = DailyCaArticle.objects.filter(
            published_date=target_date, is_published=True
        ).order_by("order_on_date")

        if category:
            articles = articles.filter(news_category=category)

        data = DailyCaArticleListSerializer(articles, many=True).data
        return Response({"date": date_str, "count": len(data), "articles": data})


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
    Last 30 days, date-grouped summary: {date, count, articles (list)}.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        cutoff = timezone.now().date() - timedelta(days=30)
        articles = DailyCaArticle.objects.filter(
            published_date__gte=cutoff, is_published=True
        ).order_by("-published_date", "order_on_date")

        # Group by date
        grouped: dict = {}
        for article in articles:
            d = str(article.published_date)
            if d not in grouped:
                grouped[d] = []
            grouped[d].append(DailyCaArticleListSerializer(article).data)

        result = [
            {"date": d, "count": len(items), "articles": items}
            for d, items in sorted(grouped.items(), reverse=True)
        ]
        return Response({"days": len(result), "archive": result})


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

        proposals = CaDailyProposal.objects.filter(date=target_date)
        status_counts: dict = {}
        for p in proposals:
            status_counts[p.status] = status_counts.get(p.status, 0) + 1

        total = proposals.count()
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

            # Bust the today cache if publishing today's articles
            if target_date == timezone.now().date():
                cache.delete(f"daily_ca_today_{target_date}")

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
