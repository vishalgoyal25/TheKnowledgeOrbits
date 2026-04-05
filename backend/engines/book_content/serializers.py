"""
Book Content Engine — Serializers
Exposes the 3-Layer Quality Engine output via DRF.

Serializer map:
  BookContentSerializer       → Full article reader (all fields)
  BookContentListSerializer   → Lightweight list (no heavy markdown)
  TopicNodeSerializer         → Graph / navbar tree node
  TopicRelationSerializer     → Graph semantic edges
  CrossReferenceSerializer    → See Also section inside article
  BookPlanSerializer          → Subject overview + TOC metadata
  GenerationLogSerializer     → Admin monitoring panel

DO NOT confuse BookContent with article_article (marketing tool).
"""

import structlog
from rest_framework import serializers

from engines.book_content.models import (
    BookContent,
    BookPlan,
    ContentMedia,
    CrossReference,
    GenerationLog,
    TopicRelation,
)
from engines.knowledge.models import Topic

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# TOPIC NODE  (graph / navbar tree)
# ─────────────────────────────────────────────────────────────────────────────


class TopicNodeSerializer(serializers.ModelSerializer):
    """
    Lightweight Topic node for graph and navbar tree rendering.
    Used by:
      GET /api/v1/book/tree/{subject_id}/
      GET /api/v1/book/graph/{subject_id}/
      GET /api/v1/book/graph/{subject_id}/node/{topic_id}/children/
    """

    parent_topic_id = serializers.UUIDField(
        source="parent_topic.id",
        read_only=True,
        default=None,
        help_text="UUID of parent topic. Null for root-level nodes.",
    )
    quality_score = serializers.SerializerMethodField(
        help_text="Quality score from associated BookContent. Null if not yet generated.",
    )
    graph_position = serializers.SerializerMethodField(
        help_text="Reserved for future graph layout coordinates {x, y}. Currently null.",
    )

    class Meta:
        model = Topic
        fields = [
            "id",
            "name",
            "node_type",
            "content_status",
            "parent_topic_id",
            "quality_score",
            "graph_position",
            "order_index",
            "difficulty_level",
        ]
        read_only_fields = fields

    def get_quality_score(self, obj: Topic) -> float | None:
        """Pull quality_score from related BookContent if it exists."""
        try:
            return obj.book_content.quality_score
        except BookContent.DoesNotExist:
            return None

    def get_graph_position(self, obj: Topic) -> dict | None:
        """
        Placeholder for future pgvector / force-graph layout coordinates.
        Returns None until the graph layout engine is implemented.
        """
        return None


# ─────────────────────────────────────────────────────────────────────────────
# TOPIC RELATION  (graph semantic edges)
# ─────────────────────────────────────────────────────────────────────────────


class TopicRelationSerializer(serializers.ModelSerializer):
    """
    Semantic edge between two topic nodes.
    Used by:
      GET /api/v1/book/graph/{subject_id}/  (edges array)
    """

    source_topic_id = serializers.UUIDField(
        source="source_topic.id",
        read_only=True,
    )
    source_topic_name = serializers.CharField(
        source="source_topic.name",
        read_only=True,
    )
    target_topic_id = serializers.UUIDField(
        source="target_topic.id",
        read_only=True,
    )
    target_topic_name = serializers.CharField(
        source="target_topic.name",
        read_only=True,
    )

    class Meta:
        model = TopicRelation
        fields = [
            "id",
            "source_topic_id",
            "source_topic_name",
            "target_topic_id",
            "target_topic_name",
            "relation_type",
            "similarity_score",
            "is_auto_detected",
            "created_at",
        ]
        read_only_fields = fields


# ─────────────────────────────────────────────────────────────────────────────
# CROSS REFERENCE  (See Also section inside article reader)
# ─────────────────────────────────────────────────────────────────────────────


class CrossReferenceSerializer(serializers.ModelSerializer):
    """
    Article-to-article cross-reference link.
    Injected by Layer 3 Coherence Engine.
    Used by:
      GET /api/v1/book/content/{topic_id}/
      GET /api/v1/book/content/{topic_id}/cross-references/
    """

    target_topic_id = serializers.UUIDField(
        source="target_content.topic.id",
        read_only=True,
        help_text="UUID of the target topic node.",
    )
    target_topic_name = serializers.CharField(
        source="target_content.topic.name",
        read_only=True,
        help_text="Name of the referenced article's topic.",
    )

    class Meta:
        model = CrossReference
        fields = [
            "id",
            "target_topic_id",
            "target_topic_name",
            "ref_type",
            "ref_text",
            "display_label",
            "created_at",
        ]
        read_only_fields = fields


# ─────────────────────────────────────────────────────────────────────────────
# CONTENT MEDIA  (Cloudinary image/infographic assets)
# ─────────────────────────────────────────────────────────────────────────────


class ContentMediaSerializer(serializers.ModelSerializer):
    """
    Media asset linked to a BookContent article.
    Populated by admin via Cloudinary dashboard → Django Admin inline.
    Frontend uses `position_marker` to match infographic blockquote nodes,
    then replaces the placeholder with a <Image> if `cloudinary_url` is present.
    Used by:
      GET /api/v1/book/content/{topic_id}/  (nested in BookContentSerializer)
    """

    class Meta:
        model = ContentMedia
        fields = [
            "id",
            "media_type",
            "cloudinary_url",
            "position_marker",
            "alt_text",
            "caption",
            "display_order",
        ]
        read_only_fields = fields


# ─────────────────────────────────────────────────────────────────────────────
# BOOK CONTENT — FULL  (article reader)
# ─────────────────────────────────────────────────────────────────────────────


class BookContentSerializer(serializers.ModelSerializer):
    """
    Full article content for the reader panel.
    Includes content_markdown, formatted_content, and nested cross_references.
    Used by:
      GET /api/v1/book/content/{topic_id}/
    """

    topic_id = serializers.UUIDField(
        source="topic.id",
        read_only=True,
    )
    topic_name = serializers.CharField(
        source="topic.name",
        read_only=True,
    )
    subject_name = serializers.CharField(
        source="subject.name",
        read_only=True,
    )
    cross_references = CrossReferenceSerializer(
        source="outgoing_references",
        many=True,
        read_only=True,
        help_text="See Also links injected by Layer 3 Coherence Engine.",
    )
    media_assets = ContentMediaSerializer(
        source="media_assets",
        many=True,
        read_only=True,
        help_text="Cloudinary media assets linked to this article (images, infographics).",
    )
    # Render formatted_content if available, else fall back to content_markdown.
    # Frontend uses this single field — no conditional logic needed in React.
    render_content = serializers.SerializerMethodField(
        help_text="Formatted content if available, otherwise raw markdown.",
    )

    class Meta:
        model = BookContent
        fields = [
            "id",
            "topic_id",
            "topic_name",
            "subject_name",
            "content_markdown",
            "formatted_content",
            "render_content",
            "word_count",
            "quality_score",
            "generation_pass",
            "source_mode",
            "has_tables",
            "has_media",
            "is_published",
            "cross_references",
            "media_assets",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_render_content(self, obj: BookContent) -> str:
        """
        Returns formatted_content if populated (Phase 4.5B tables + callouts).
        Falls back to content_markdown for articles not yet formatted.
        """
        return (
            obj.formatted_content
            if obj.formatted_content.strip()
            else obj.content_markdown
        )


# ─────────────────────────────────────────────────────────────────────────────
# BOOK CONTENT — LIST  (lightweight, no heavy markdown)
# ─────────────────────────────────────────────────────────────────────────────


class BookContentListSerializer(serializers.ModelSerializer):
    """
    Lightweight list serializer — omits content_markdown and formatted_content.
    Used for index/listing pages where full markdown is not needed.
    Used by:
      GET /api/v1/book/subjects/   (embedded in subject overview)
      Any paginated list endpoint
    """

    topic_id = serializers.UUIDField(
        source="topic.id",
        read_only=True,
    )
    topic_name = serializers.CharField(
        source="topic.name",
        read_only=True,
    )
    node_type = serializers.CharField(
        source="topic.node_type",
        read_only=True,
    )

    class Meta:
        model = BookContent
        fields = [
            "id",
            "topic_id",
            "topic_name",
            "node_type",
            "word_count",
            "quality_score",
            "source_mode",
            "has_tables",
            "has_media",
            "is_published",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


# ─────────────────────────────────────────────────────────────────────────────
# BOOK PLAN  (subject overview + TOC metadata)
# ─────────────────────────────────────────────────────────────────────────────


class BookPlanSerializer(serializers.ModelSerializer):
    """
    Book Intelligence Plan for a subject.
    Exposes TOC, concept registry, prerequisite chains, and progress stats.
    Used by:
      GET /api/v1/book/subjects/
    """

    subject_id = serializers.UUIDField(
        source="subject.id",
        read_only=True,
    )
    subject_name = serializers.CharField(
        source="subject.name",
        read_only=True,
    )
    completion_pct = serializers.SerializerMethodField(
        help_text="Percentage of planned topics that have been generated (0–100).",
    )

    class Meta:
        model = BookPlan
        fields = [
            "id",
            "subject_id",
            "subject_name",
            "generation_status",
            "topics_planned",
            "topics_completed",
            "avg_quality_score",
            "completion_pct",
            "toc_json",
            "reading_order",
            "prerequisite_chains",
            # concept_registry intentionally excluded — internal engine data, not for UI
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_completion_pct(self, obj: BookPlan) -> float:
        """Returns percentage of topics generated. Returns 0.0 if nothing planned yet."""
        if not obj.topics_planned:
            return 0.0
        return round((obj.topics_completed / obj.topics_planned) * 100, 1)


# ─────────────────────────────────────────────────────────────────────────────
# GENERATION LOG  (admin monitoring)
# ─────────────────────────────────────────────────────────────────────────────


class GenerationLogSerializer(serializers.ModelSerializer):
    """
    Per-run generation log for admin monitoring and crash-recovery audit.
    Used by:
      GET /api/v1/book/generation-log/
    """

    status_icon = serializers.SerializerMethodField(
        help_text="Visual status indicator for admin UI: ✅ success | ❌ failed | ⏭️ skipped",
    )

    class Meta:
        model = GenerationLog
        fields = [
            "id",
            "topic_name",
            "subject_name",
            "status",
            "status_icon",
            "nodes_created",
            "relations_created",
            "cross_refs_created",
            "quality_score",
            "word_count",
            "generation_time_seconds",
            "error_message",
            "created_at",
        ]
        read_only_fields = fields

    def get_status_icon(self, obj: GenerationLog) -> str:
        icons = {
            "success": "✅",
            "failed": "❌",
            "skipped": "⏭️",
        }
        return icons.get(obj.status, "⚪")
