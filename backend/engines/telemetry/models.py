"""
Telemetry Engine Models

Tables:
- telemetry_visit_log     — one row per server-visible request (after filtering)
- telemetry_content_read  — one row per reader, per content item, per day

Scope
─────
`engines.analytics` is the LEARNER-facing study feature (what a user did:
articles read, quizzes taken, streaks, insights). This engine is
infrastructure telemetry (what the server saw). The two must not merge.

No user ForeignKey exists here by design. `is_authenticated` is a boolean, so
a row records *that* a request was signed in, never *who* signed it — which
keeps the whole table pseudonymous under the DPDP Act.

Why two models
──────────────
Public pages are ISR-cached on Vercel's CDN, so a reader never reaches
Django. VisitLog therefore measures API traffic, error paths and abuse
patterns — NOT readership. ContentRead is written by a client-side beacon and
is the only source that can answer "which article is read most".

Storage budget (Supabase has ~220 MB of headroom)
─────────────────────────────────────────────────
VisitLog     ~500 B/row including indexes. At ~2,000 filtered requests/day
             with 30-day retention that is ~30 MB steady state.
ContentRead  ~250 B/row. Capped by the unique constraint below to at most one
             row per (content, visitor, day), so growth tracks real
             readership rather than request volume — a few MB at current
             traffic.

Re-check both against real volume one week after launch. Retention is
configurable via TELEMETRY_RETENTION_DAYS; neither table is allowed to grow
unbounded, because a full storeroom fails API writes, not just analytics.
"""

import uuid

from django.db import models

# Field caps. Exported so the middleware and beacon truncate to the SAME
# limits the columns enforce — a value silently longer than its column raises
# in production and would take a request down with it.
MAX_PATH_LENGTH = 512
MAX_REFERRER_LENGTH = 512
MAX_USER_AGENT_LENGTH = 512
MAX_CONTENT_ID_LENGTH = 255

# SHA-256 hex digest. Fixed width — the salted hash is always 64 characters.
IP_HASH_LENGTH = 64


class VisitLog(models.Model):
    """
    One request that actually reached Django, after filtering.

    Deliberately NOT a page-view counter: CDN-cached pages never arrive here.
    Use ContentRead for readership. Use this for API traffic, error paths,
    hot endpoints and abuse patterns.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )

    path = models.CharField(
        max_length=MAX_PATH_LENGTH,
        help_text="Request path, truncated to the column width",
    )

    method = models.CharField(
        max_length=10,
        help_text="HTTP method (GET, POST, ...)",
    )

    status_code = models.PositiveSmallIntegerField(
        help_text="Response status — makes error-path analysis possible",
    )

    referrer = models.CharField(
        max_length=MAX_REFERRER_LENGTH,
        blank=True,
        default="",
        help_text="Referer header if present, truncated. Empty string, never NULL",
    )

    user_agent = models.CharField(
        max_length=MAX_USER_AGENT_LENGTH,
        blank=True,
        default="",
        help_text="User-Agent header, truncated. Empty string, never NULL",
    )

    ip_hash = models.CharField(
        max_length=IP_HASH_LENGTH,
        help_text=(
            "Salted SHA-256 of the client IP. The raw IP is NEVER stored, "
            "logged or sent to Sentry. Salt comes from TELEMETRY_IP_SALT — an "
            "unsalted hash of an IPv4 address is trivially reversible, since "
            "the whole address space enumerates in seconds"
        ),
    )

    is_authenticated = models.BooleanField(
        default=False,
        help_text=(
            "Whether the request was signed in. Boolean only — there is no "
            "user FK on this model, so a row can never identify a person"
        ),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the request was served",
    )

    class Meta:
        db_table = "telemetry_visit_log"
        ordering = ["-created_at"]
        # Three indexes, each earning its write cost on a table where storage
        # is the binding constraint:
        #   created_at    — retention prune + "recent traffic"
        #   path          — "which endpoints are hot"
        #   status_code   — "what is failing"
        # is_authenticated is deliberately NOT indexed: a two-value column has
        # too little selectivity for the planner to use one.
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["path", "-created_at"]),
            models.Index(fields=["status_code", "-created_at"]),
        ]
        verbose_name = "Visit Log"
        verbose_name_plural = "Visit Logs"

    def __str__(self) -> str:
        return f"{self.method} {self.path} [{self.status_code}]"


class ContentRead(models.Model):
    """
    One reader, one piece of content, one day.

    Written by the client-side beacon, which is a POST and therefore immune to
    every caching layer between the reader and Django — the CDN, the browser
    cache, and the Cache-Control headers set in core/middleware.py.

    Content is referenced by type + text id, never a ForeignKey:
      - a cross-engine FK would violate the no-cross-engine-DB-access rule;
      - keeping it loose means deleting an article does not cascade away its
        read history.
    """

    CONTENT_TYPE_DAILY_CA = "daily_ca_article"
    CONTENT_TYPE_CONCEPT = "concept"
    CONTENT_TYPE_ARTICLE = "article"

    CONTENT_TYPE_CHOICES = [
        (CONTENT_TYPE_DAILY_CA, "Daily CA Article"),
        (CONTENT_TYPE_CONCEPT, "Concept"),
        (CONTENT_TYPE_ARTICLE, "Generated Article"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )

    content_type = models.CharField(
        max_length=32,
        choices=CONTENT_TYPE_CHOICES,
        help_text="Which kind of content was read",
    )

    content_id = models.CharField(
        max_length=MAX_CONTENT_ID_LENGTH,
        help_text=(
            "Slug or UUID as text. Intentionally not a ForeignKey — see the "
            "class docstring"
        ),
    )

    ip_hash = models.CharField(
        max_length=IP_HASH_LENGTH,
        help_text="Salted SHA-256 of the client IP, used only for daily dedupe",
    )

    is_authenticated = models.BooleanField(
        default=False,
        help_text="Whether the reader was signed in. Boolean only, no user FK",
    )

    read_date = models.DateField(
        help_text=(
            "Local date of the read. Stored explicitly so the unique "
            "constraint below can collapse repeat reads to one row per day"
        ),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the beacon fired",
    )

    class Meta:
        db_table = "telemetry_content_read"
        ordering = ["-created_at"]
        constraints = [
            # Dedupe enforced by Postgres, not by application logic. A refresh
            # cannot inflate counts, and the check is atomic — a read-then-write
            # guard would race across the 8 gunicorn threads sharing the dyno.
            # It also CAPS growth: at most one row per content, per reader, per
            # day, which is what keeps this table's size tied to real
            # readership instead of to traffic volume.
            models.UniqueConstraint(
                fields=["content_type", "content_id", "ip_hash", "read_date"],
                name="uniq_content_read_per_visitor_per_day",
            ),
        ]
        # The unique constraint already indexes (content_type, content_id,
        # ip_hash, read_date), so no separate dedupe index is needed. These two
        # cover the queries that constraint cannot serve.
        indexes = [
            models.Index(fields=["content_type", "content_id", "-read_date"]),
            models.Index(fields=["-created_at"]),
        ]
        verbose_name = "Content Read"
        verbose_name_plural = "Content Reads"

    def __str__(self) -> str:
        return f"{self.content_type}:{self.content_id} on {self.read_date}"
