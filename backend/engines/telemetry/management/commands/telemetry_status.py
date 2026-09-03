"""
Read-only health report for the telemetry tables.

    python manage.py telemetry_status --database=supabase

Exists as a command rather than a one-off `shell -c` because that quoting is
unusable on PowerShell (\" is not an escape there), and because this is not a
one-off: it answers three recurring questions.

1. Is X-Forwarded-For actually working in production?
   THE reason this file exists. Render sits behind a load balancer, so
   REMOTE_ADDR is the proxy — using it would hash one identical value for every
   visitor while looking perfectly correct on localhost. The only proof is live
   data: many rows but ONE distinct ip_hash means the forwarded header is being
   ignored. Reported explicitly below as a verdict, not left for the reader to
   infer from two numbers.

2. Which bots are actually hitting us?
   BOT_USER_AGENT_MARKERS in middleware.py was written from reasoning, not from
   this site's traffic. The user-agent breakdown here is what it should be
   refined against after a week of real data.

3. Is storage growing as projected?
   Supabase has ~220 MB of headroom and retention does not prune for 30 days.
   The row counts here are the early warning.

NEVER writes. Safe to run against production at any time.
"""

from typing import Any

from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS
from django.db.models import Count

from engines.telemetry.models import ContentRead, VisitLog


class Command(BaseCommand):
    help = "Read-only summary of collected telemetry."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            help="Database alias. Use --database=supabase for production.",
        )
        parser.add_argument(
            "--top",
            type=int,
            default=10,
            help="How many rows per breakdown (default 10).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        db: str = options["database"]
        top: int = options["top"]

        visits = VisitLog.objects.using(db)
        reads = ContentRead.objects.using(db)

        self._header(f"TELEMETRY STATUS — {db}")

        # ── VisitLog ─────────────────────────────────────────────────────────
        total = visits.count()
        visitors = visits.values("ip_hash").distinct().count()

        self.stdout.write(f"\nVisitLog: {total} rows, {visitors} distinct visitors")

        if total == 0:
            self.stdout.write(
                "  No rows yet. Either no browser traffic has reached the API, or "
                "TELEMETRY_ENABLED / TELEMETRY_IP_SALT are unset."
            )
        else:
            self._forwarded_header_verdict(total, visitors)
            self._breakdown(visits, "path", "Top paths", top)
            self._breakdown(visits, "status_code", "Status codes", top)
            self._breakdown(visits, "user_agent", "User agents (refine bot list)", top)

            authed = visits.filter(is_authenticated=True).count()
            self.stdout.write(f"\n  Authenticated: {authed} / {total}")

            oldest = visits.order_by("created_at").values_list("created_at", flat=True)
            self.stdout.write(f"  Oldest row: {oldest.first()}")

        # ── ContentRead ──────────────────────────────────────────────────────
        read_total = reads.count()
        self.stdout.write(f"\nContentRead: {read_total} rows")

        if read_total == 0:
            self.stdout.write(
                "  Expected while the frontend beacon is unshipped — it lands with "
                "the G2 batch."
            )
        else:
            self._breakdown(reads, "content_id", "Most read", top)
            self._breakdown(reads, "content_type", "By type", top)

        self.stdout.write("")

    # ── helpers ──────────────────────────────────────────────────────────────

    def _header(self, text: str) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n{text}"))
        self.stdout.write("=" * len(text))

    def _forwarded_header_verdict(self, total: int, visitors: int) -> None:
        """
        The F-I check. Stated as a verdict because two bare numbers are easy to
        read past, and this failure mode is invisible everywhere except here.
        """
        if visitors == 1 and total > 5:
            self.stdout.write(
                self.style.ERROR(
                    "  X-FORWARDED-FOR CHECK: FAILED — every row shares one "
                    "ip_hash. The proxy address is being recorded instead of the "
                    "visitor's. See client_ip() in utils.py."
                )
            )
        elif visitors <= 1:
            self.stdout.write(
                self.style.WARNING(
                    "  X-Forwarded-For check: inconclusive — too few rows to tell "
                    "one visitor from a broken header. Re-run after more traffic."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  X-Forwarded-For check: OK — {visitors} distinct visitors "
                    "across the rows, so the forwarded header is being honoured."
                )
            )

    def _breakdown(self, queryset: Any, field: str, title: str, limit: int) -> None:
        rows = queryset.values(field).annotate(n=Count("id")).order_by("-n")[:limit]
        self.stdout.write(f"\n  {title}:")
        for row in rows:
            value = str(row[field])[:70] or "(empty)"
            self.stdout.write(f"    {row['n']:>6}  {value}")
