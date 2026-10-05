"""Acquisition layer: where material comes from, and what we actually fetched.

``DfSource``   -- a registry row. Adding a source is configuration, not code.
``DfArtifact`` -- one fetched document, byte-exact, content-hashed.

The captured/derived rule (06_DESIGN.md 1.2)
--------------------------------------------
Both models here are CAPTURED, so neither carries ``processing_version``. The
bytes do not have a version; the interpretation does. A re-parse produces new
``DfChunk`` and ``DfAtom`` rows pointing at the SAME unchanged artifact, which
is what makes re-processing safe.

Contract 1 -- encoding integrity
--------------------------------
``encoding_used`` is stored because ``char_start``/``char_end`` on an atom are
offsets into decoded text. If the encoding is ever resolved differently on a
re-parse, every offset shifts and the citation chain breaks silently. This
column is what lets a re-parse from the archive reproduce identical offsets.

Nothing here is bound to anything else
--------------------------------------
``tier`` and ``adapter`` are orthogonal: any tier may use any adapter. Sources
change shape -- PIB could replace its RSS with a JSON API, or keep RSS and
rename its fields. Three mechanisms absorb that without a schema change:

1. ``adapter`` is one value on one row. RSS -> JSON API is one UPDATE.
2. ``config`` carries per-source adapter settings, so a renamed field is a
   config edit rather than an ``if source.name == ...`` branch in code.
3. ``last_yield_count`` detects silent shape drift -- HTTP 200, clean parse,
   zero items -- which no status code can reveal.

And the recovery path is already structural: raw bytes live in S3 regardless of
whether extraction succeeded, so a corrected adapter re-runs over material
already fetched. A broken adapter costs interpretation, never acquisition.
"""

import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class DfSource(models.Model):
    """A registry row describing one place material comes from.

    Adding PIB is one row with ``adapter="rss"``. Adding RBI is one row with
    ``adapter="json_api"``. No factory code changes -- that is the whole point
    of Contract 2.

    Separate from ``current_affairs.CASource`` by decision (06_DESIGN.md 5.1):
    that table is read by live crons and is current-affairs-shaped. Two
    registries coexist; this one is product-agnostic.
    """

    TIER_T1 = "T1"
    TIER_T2 = "T2"
    TIER_T3 = "T3"
    TIER_T4 = "T4"
    TIER_CHOICES = [
        (TIER_T1, "T1 - Indian primary (PIB, ministries, RBI, courts, BIS)"),
        (TIER_T2, "T2 - International primary (UN, FAO, IUCN, World Bank)"),
        (TIER_T3, "T3 - Reputable press (event detection ONLY, never cited)"),
        (TIER_T4, "T4 - Generated or encyclopaedic (context ONLY, never cited)"),
    ]

    # Citable tiers, named once so no caller hardcodes the pair. T3/T4 are
    # retrieval context only -- citing them would make verification circular,
    # which is the finding that justifies this whole engine (00_MASTER_RECAP 3.6).
    CITABLE_TIERS = (TIER_T1, TIER_T2)

    ADAPTER_CHOICES = [
        ("rss", "RSS / Atom feed"),
        ("json_api", "JSON API"),
        ("html", "HTML page scrape"),
        ("pdf", "PDF document"),
        ("dataset", "CSV / XLSX dataset"),
        ("transcript", "Transcript"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the source",
    )
    name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Human-readable identity, e.g. 'PIB - Ministry of Environment'",
    )
    tier = models.CharField(
        max_length=2,
        choices=TIER_CHOICES,
        help_text=(
            "Evidence tier. Only T1/T2 may be cited as evidence; T3 is event "
            "detection and T4 is retrieval context. Snapshotted onto each atom "
            "at extraction time, so re-grading this never rewrites past citations."
        ),
    )
    adapter = models.CharField(
        max_length=20,
        choices=ADAPTER_CHOICES,
        help_text=(
            "Fetcher adapter to use. One per SHAPE of source, not per source. "
            "Independent of `tier` -- any tier may use any adapter, and a source "
            "that switches from RSS to a JSON API is one UPDATE here, with no "
            "migration and no code change. Adding a new adapter is a `choices` "
            "change, which Django emits no SQL for. A source needing two shapes "
            "(an RSS index plus linked PDFs) is TWO registry rows, not a chain."
        ),
    )
    endpoint = models.TextField(
        unique=True,
        help_text=(
            "Feed URL, API base, or page URL. TextField rather than URLField "
            "because government endpoints carry long query strings and some are "
            "not URL-validator clean."
        ),
    )
    category = models.CharField(
        max_length=50,
        blank=True,
        help_text="Free-form grouping, e.g. 'ministry', 'press', 'dataset', 'court'",
    )
    jurisdiction = models.CharField(
        max_length=50,
        blank=True,
        help_text="e.g. 'india', 'international'. Used for blueprint balance, not filtering.",
    )
    language = models.CharField(
        max_length=10,
        default="en",
        help_text="ISO code of the source's primary language",
    )
    licence = models.CharField(
        max_length=200,
        blank=True,
        help_text="Licence or terms-of-use note. Blank means not yet established.",
    )
    credibility_score = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="0.0-1.0 manual confidence in this source, within its tier",
    )
    priority = models.IntegerField(
        default=100,
        help_text="Lower runs first when the fetch queue is saturated",
    )
    active = models.BooleanField(
        default=True,
        help_text=(
            "Whether to fetch from this source. Set False automatically after "
            "repeated failures; failure is scoped to one source and never stops "
            "the cycle (00_MASTER_RECAP 25.4)."
        ),
    )
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Adapter-specific settings for THIS source: field mappings, CSS "
            "selectors, date formats, pagination params, extra headers. This is "
            "what makes Contract 2 literally true -- adding source 50 is a row, "
            "not a code change. An adapter reads this and NEVER hardcodes "
            "per-source handling; rss_scraper.py does hardcode it for two "
            "sources, and that approach does not survive fifty. Empty dict means "
            "the adapter's defaults are sufficient."
        ),
    )
    last_ok_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last fetch that returned HTTP 200 with parseable content",
    )
    last_yield_count = models.IntegerField(
        null=True,
        blank=True,
        help_text=(
            "Items extracted on the last successful fetch. SHAPE-DRIFT DETECTOR: "
            "a source that returns HTTP 200, parses cleanly, and yields 0 items "
            "where it used to yield 40 has changed shape -- its adapter config "
            "needs updating. Status alone cannot see this, which is the same "
            "blind spot as treating `bozo` as fatal (00_MASTER_RECAP 7.5). Null "
            "means never successfully fetched."
        ),
    )
    last_yield_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When last_yield_count was recorded",
    )
    failure_count = models.IntegerField(
        default=0,
        help_text="Consecutive failures. Reset to 0 on success.",
    )
    last_error = models.TextField(
        blank=True,
        help_text="Last error text, including the real HTTP status. The status IS the diagnosis.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Row creation timestamp"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Row last-modified timestamp"
    )

    class Meta:
        db_table = "df_source"
        ordering = ["priority", "name"]
        indexes = [
            # The hot query: "which sources do I fetch next?"
            models.Index(
                fields=["active", "priority"], name="df_source_active_prio_idx"
            ),
            # The evidence query: "which sources may be cited?"
            models.Index(fields=["tier", "active"], name="df_source_tier_active_idx"),
            models.Index(fields=["adapter"], name="df_source_adapter_idx"),
        ]
        verbose_name = "Data Factory source"
        verbose_name_plural = "Data Factory sources"

    def __str__(self) -> str:
        return f"[{self.tier}] {self.name}"

    @property
    def is_citable(self) -> bool:
        """Whether atoms from this source may be used as evidence."""
        return self.tier in self.CITABLE_TIERS


class DfArtifact(models.Model):
    """One fetched document. Immutable once written.

    S3 holds the raw bytes; this row holds what we know about them. The raw
    archive is what makes the Factory non-rigid: a new extraction angle re-runs
    over the archive without re-fetching anything.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the artifact",
    )
    source = models.ForeignKey(
        DfSource,
        on_delete=models.PROTECT,
        related_name="artifacts",
        help_text=(
            "The source this was fetched from. PROTECT, not CASCADE: artifacts "
            "are evidence. Deleting a registry row must never silently destroy "
            "the documents that back published citations."
        ),
    )
    content_hash = models.CharField(
        max_length=64,
        unique=True,
        help_text=(
            "SHA-256 of the raw bytes, hex. Dedup level 1 and the idempotency "
            "key for fetching -- re-fetching an unchanged document is a no-op."
        ),
    )
    s3_key = models.TextField(
        blank=True,
        help_text=(
            "Object key, raw/<source_id>/<yyyy>/<mm>/<dd>/<content_hash>.<ext>. "
            "Blank during Act 0, which has no S3 and stores nothing remotely."
        ),
    )
    source_url = models.TextField(
        help_text="The exact URL fetched, which may differ from the source endpoint",
    )
    http_status = models.IntegerField(
        null=True,
        blank=True,
        help_text=(
            "Real HTTP status. Recorded because a 403 HTML body parsed as XML "
            "reported itself as malformed XML and hid the true cause for weeks "
            "(00_MASTER_RECAP 7.5a). A non-200 body is never parsed."
        ),
    )
    declared_content_type = models.CharField(
        max_length=200,
        blank=True,
        help_text="Raw Content-Type header, kept for diagnosing encoding disputes",
    )
    encoding_used = models.CharField(
        max_length=40,
        help_text=(
            "Encoding actually used to decode the bytes. Contract 1: resolve "
            "explicitly, never let a parser guess. requests defaults to "
            "ISO-8859-1 when charset is omitted, which mangles UTF-8 silently."
        ),
    )
    byte_size = models.IntegerField(
        default=0,
        help_text="Size of the raw bytes, for storage accounting",
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "The source's own publication timestamp, where available. Drives "
            "ingestion-freshness SLO measurement; null when unparseable."
        ),
    )
    retrieved_at = models.DateTimeField(
        help_text="When we fetched it. Set explicitly, never auto_now_add -- a "
        "re-parse from the archive must preserve the original fetch time.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Row creation timestamp"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Row last-modified timestamp"
    )

    class Meta:
        db_table = "df_artifact"
        ordering = ["-retrieved_at"]
        indexes = [
            # Re-processing is source-centric: "this source, this date range".
            models.Index(
                fields=["source", "-retrieved_at"],
                name="df_artifact_src_retr_idx",
            ),
            # Ingestion freshness: publication -> atom available.
            models.Index(fields=["-published_at"], name="df_artifact_pub_idx"),
        ]
        verbose_name = "Data Factory artifact"
        verbose_name_plural = "Data Factory artifacts"

    def __str__(self) -> str:
        return f"{self.source.name} @ {self.retrieved_at:%Y-%m-%d} ({self.content_hash[:8]})"
