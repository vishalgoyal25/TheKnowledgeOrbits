"""
Management Command: Aggregate Analytics

Run daily via cron to aggregate previous day's data.

Usage:
    python manage.py aggregate_analytics
    python manage.py aggregate_analytics --date 2026-02-14
"""

from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta

from engines.analytics.services.analytics_service import get_analytics_service


class Command(BaseCommand):
    help = "Aggregate analytics for all users"

    def add_arguments(self, parser) -> Any:  # type: ignore
        parser.add_argument(
            "--date",
            type=str,
            help="Date to aggregate (YYYY-MM-DD). Defaults to yesterday.",
        )

    def handle(self, *args, **options) -> Any:  # type: ignore
        # Determine date
        if options["date"]:
            try:
                date = datetime.strptime(options["date"], "%Y-%m-%d").date()
            except ValueError:
                self.stdout.write(
                    self.style.ERROR("Invalid date format. Use YYYY-MM-DD")
                )
                return
        else:
            # Default to yesterday
            date = (timezone.now() - timedelta(days=1)).date()

        self.stdout.write(f"Aggregating analytics for {date}...")

        # Run aggregation
        analytics_service = get_analytics_service()
        count = analytics_service.aggregate_all_users(date)

        self.stdout.write(self.style.SUCCESS(f"✅ Aggregated {count} users for {date}"))
