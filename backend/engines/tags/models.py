"""
engines/tags/models.py
━━━━━━━━━━━━━━━━━━━━━━
Tags Engine — Four models:

  Tag                 — keyword labels (article chips, discovery pages)
  ArticleTag          — M2M junction: Tag ↔ any article (daily_ca or book_content)
  ConceptPage         — standalone concept explanation stubs (inline [[term]] links)
  ConceptArticleLink  — M2M junction: ConceptPage ↔ DailyCaArticle

Phase C note on ConceptArticleLink:
  DailyCaArticle (engines.daily_ca) does not exist yet (Phase E).
  daily_ca_article_id is stored as a plain UUIDField here.
  A FK constraint migration will be added in Phase E once DailyCaArticle is created.
  Max 8 concept links per article is enforced at the service layer (Phase K).

Three-entity rule (never confuse these):
  Tag          → article label   → /tags/[slug]     → aggregation page
  ConceptPage  → inline deep-link → /concepts/[slug] → concept detail page
  BookContent  → syllabus topic   → /learn/[slug]    → structured article
"""

import uuid

from django.db import models


# ── TAG TYPES ─────────────────────────────────────────────────────────────────
TAG_TYPE_CHOICES = [
    ("topic", "UPSC Topic"),
    ("subtopic", "Subtopic"),
    ("scheme", "Government Scheme"),
    ("person", "Person/Figure"),
    ("place", "Place/Geography"),
    ("organisation", "Organisation/Body"),
    ("concept", "Concept/Term"),
    ("law", "Law/Act/Treaty"),
    ("event", "Event"),
    ("other", "Other"),
]

# Content types that can carry tags
ARTICLE_CONTENT_TYPE_CHOICES = [
    ("daily_ca", "Daily CA Article"),
    ("book_content", "Static Book Content"),
]


# ── MODEL 1: Tag ──────────────────────────────────────────────────────────────


class Tag(models.Model):
    """
    Keyword tag — a permanent, reusable label for articles.

    Rules:
    - name is always lowercase-hyphenated (e.g. "nuclear-energy", "article-370")
    - slug is auto-set from name; never changed after creation
    - Tags are never deleted — set is_active=False to retire
    - Max 8 tags per article (enforced at service layer)
    - Pre-seeded 1000+ tags via seed_tags command (Phase D)
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Lowercase-hyphenated tag name (e.g. 'nuclear-energy')",
    )
    slug = models.SlugField(
        max_length=120,
        unique=True,
        help_text="URL-safe slug — auto-set from name, never changed after creation",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="1-2 sentence explanation of what this tag covers",
    )
    tag_type = models.CharField(
        max_length=20,
        choices=TAG_TYPE_CHOICES,
        default="concept",
        help_text="Classification of this tag for filtering and discovery",
    )
    usage_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of articles carrying this tag — updated on every tag/untag",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive tags are hidden from UI but never deleted",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tag"
        ordering = ["-usage_count", "name"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["tag_type"]),
            models.Index(fields=["-usage_count"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.tag_type})"


# ── MODEL 2: ArticleTag ───────────────────────────────────────────────────────


class ArticleTag(models.Model):
    """
    M2M junction linking a Tag to any article.

    Uses a generic FK pattern (content_type + object_id) so both
    DailyCaArticle and BookContent articles can share the same tag table.

    Max 8 tags per article enforced at service layer (TagService).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    tag = models.ForeignKey(
        Tag,
        on_delete=models.CASCADE,
        related_name="article_tags",
        help_text="The tag being applied",
    )
    content_type = models.CharField(
        max_length=20,
        choices=ARTICLE_CONTENT_TYPE_CHOICES,
        help_text="Which article type this tag is applied to",
    )
    object_id = models.UUIDField(
        help_text="PK of the linked article (DailyCaArticle or BookContent)",
    )
    relevance = models.FloatField(
        default=1.0,
        help_text="Tag relevance score 0.0–1.0 (1.0 = primary, <1.0 = secondary)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "article_tag"
        unique_together = [["tag", "content_type", "object_id"]]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["tag", "content_type"]),
            models.Index(fields=["object_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.tag.name} → {self.content_type}:{self.object_id}"


# ── MODEL 3: ConceptPage ──────────────────────────────────────────────────────


class ConceptPage(models.Model):
    """
    Standalone concept explanation page — created organically during CA generation
    when the LLM wraps a high-value term in [[double brackets]].

    Lifecycle:
      Creation   → brief_description generated (1 GROQ call), body_md empty, is_content_ready=False
      Future     → body_md populated in a dedicated generation phase
      Live       → is_content_ready=True, full page rendered at /concepts/[slug]

    This is NOT a keyword tag and NOT a syllabus topic.
    It is a standalone knowledge unit for deep contextual explanation.

    Examples: "CLNDA", "Viksit Bharat 2047", "101st Constitutional Amendment",
              "Sendai Framework", "PM-WANI", "ABDM"
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(
        max_length=300,
        help_text="Full name of the concept (e.g. 'Civil Liability for Nuclear Damage Act')",
    )
    slug = models.SlugField(
        max_length=350,
        unique=True,
        help_text="URL-safe slug — auto-set at creation, never changed",
    )
    brief_description = models.TextField(
        blank=True,
        default="",
        help_text="2-3 line LLM-generated description, created at stub creation time",
    )
    body_md = models.TextField(
        blank=True,
        default="",
        help_text="Full markdown content — empty until concept page generation phase runs",
    )
    is_content_ready = models.BooleanField(
        default=False,
        db_index=True,
        help_text="False = stub only (brief_description only). True = full page live.",
    )
    usage_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of CA articles this concept has been linked from",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "concept_page"
        ordering = ["-usage_count", "name"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["-usage_count"]),
            models.Index(fields=["is_content_ready"]),
        ]

    def __str__(self) -> str:
        status = "full" if self.is_content_ready else "stub"
        return f"{self.name} [{status}]"


# ── MODEL 4: ConceptArticleLink ───────────────────────────────────────────────


class ConceptArticleLink(models.Model):
    """
    M2M junction linking a ConceptPage to a DailyCaArticle.

    Phase C note:
      daily_ca_article_id is a plain UUIDField here because DailyCaArticle
      (engines.daily_ca) does not exist yet. The actual FK constraint and
      CASCADE behaviour will be added via migration in Phase E once
      DailyCaArticle is created.

    Max 8 concept links per article enforced at service layer (ConceptPageResolver).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    concept_page = models.ForeignKey(
        ConceptPage,
        on_delete=models.CASCADE,
        related_name="article_links",
        help_text="The concept page being linked",
    )
    # Phase C: plain UUID — FK constraint added in Phase E migration
    daily_ca_article_id = models.UUIDField(
        help_text="PK of the DailyCaArticle this concept is linked from "
        "(FK constraint to daily_ca.DailyCaArticle added in Phase E)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "concept_article_link"
        unique_together = [["concept_page", "daily_ca_article_id"]]
        indexes = [
            models.Index(fields=["concept_page"]),
            models.Index(fields=["daily_ca_article_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.concept_page.name} → article:{self.daily_ca_article_id}"
