"""
engines/daily_ca/admin.py
━━━━━━━━━━━━━━━━━━━━━━━━━
Phase L — Daily CA Engine Django Admin registration.
"""

from django.contrib import admin

from engines.daily_ca.models import CaDailyProposal, DailyCaArticle, DailyCaStaticLink


@admin.register(CaDailyProposal)
class CaDailyProposalAdmin(admin.ModelAdmin):
    list_display = [
        "title", "date", "status", "subject_name", "gs_paper",
        "relevance_score", "created_at",
    ]
    list_filter = ["status", "date", "subject_name", "gs_paper"]
    search_fields = ["title", "description"]
    readonly_fields = [
        "id", "ca_chunk_ids", "source_urls", "relevance_score",
        "generated_article_id", "created_at",
    ]
    ordering = ["-date", "-relevance_score"]
    date_hierarchy = "date"

    actions = ["approve_proposals"]

    @admin.action(description="Approve selected proposals")
    def approve_proposals(self, request, queryset):
        from django.utils import timezone
        count = queryset.filter(status__in=["pending", "failed"]).update(
            status="approved", approved_at=timezone.now()
        )
        self.message_user(request, f"{count} proposal(s) approved.")


@admin.register(DailyCaArticle)
class DailyCaArticleAdmin(admin.ModelAdmin):
    list_display = [
        "title", "published_date", "subject_name", "gs_paper",
        "quality_score", "is_published", "order_on_date", "created_at",
    ]
    list_filter = ["is_published", "published_date", "subject_name", "gs_paper"]
    search_fields = ["title", "slug"]
    readonly_fields = [
        "id", "slug", "body_md", "body_md_processed", "ca_chunk_ids",
        "sources_used", "generation_metadata", "quality_score", "created_at", "updated_at",
    ]
    ordering = ["-published_date", "order_on_date"]
    date_hierarchy = "published_date"

    actions = ["publish_articles", "unpublish_articles"]

    @admin.action(description="Publish selected articles")
    def publish_articles(self, request, queryset):
        count = queryset.update(is_published=True)
        self.message_user(request, f"{count} article(s) published.")

    @admin.action(description="Unpublish selected articles")
    def unpublish_articles(self, request, queryset):
        count = queryset.update(is_published=False)
        self.message_user(request, f"{count} article(s) unpublished.")


@admin.register(DailyCaStaticLink)
class DailyCaStaticLinkAdmin(admin.ModelAdmin):
    list_display = ["daily_article", "book_content", "link_reason", "created_at"]
    list_filter = ["link_reason"]
    readonly_fields = ["id", "created_at"]
