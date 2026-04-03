"""
Book Content Engine — Views
Exposes the 3-Layer Quality Engine output via DRF API endpoints.

Endpoints:
  GET /api/v1/book/subjects/
  GET /api/v1/book/tree/{subject_id}/
  GET /api/v1/book/graph/{subject_id}/
  GET /api/v1/book/graph/{subject_id}/node/{topic_id}/children/
  GET /api/v1/book/content/{topic_id}/
  GET /api/v1/book/content/{topic_id}/cross-references/
  GET /api/v1/book/generation-log/   (staff only)

Auth pattern:
  Public  (AllowAny)  — subjects, tree, graph, children, content, cross-references
  Staff   (IsAdminUser) — generation-log only
"""

import structlog
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from engines.book_content.models import (
    BookContent,
    CrossReference,
    GenerationLog,
    TopicRelation,
)
from engines.book_content.serializers import (
    BookContentSerializer,
    BookPlanSerializer,
    CrossReferenceSerializer,
    GenerationLogSerializer,
    TopicNodeSerializer,
    TopicRelationSerializer,
)
from engines.knowledge.models import Module, Subject, Topic

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def _build_topic_tree(topic: Topic) -> dict:
    """
    Recursively builds a nested dict for a single topic node.
    Attaches quality_score from BookContent if generated.
    Depth: topic → subtopics → sub_subtopics (follows parent_topic FK chain).
    """
    quality_score = None
    try:
        quality_score = topic.book_content.quality_score
    except BookContent.DoesNotExist:
        pass

    node = {
        "id": str(topic.id),
        "name": topic.name,
        "node_type": topic.node_type,
        "content_status": topic.content_status,
        "quality_score": quality_score,
        "order_index": topic.order_index,
        "difficulty_level": topic.difficulty_level,
        "subtopics": [],
    }

    for child in topic.subtopics.filter(is_active=True).order_by("order_index", "name"):
        node["subtopics"].append(_build_topic_tree(child))

    return node


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/book/subjects/
# ─────────────────────────────────────────────────────────────────────────────


@api_view(["GET"])
@permission_classes([AllowAny])
def subject_list(request: Request) -> Response:
    """
    Returns all active subjects enriched with their BookPlan status.
    Subjects with no plan yet return a minimal stub so the frontend
    can still render them (just with zero progress).
    Used by: subject selector in frontend.
    """
    subjects = Subject.objects.filter(is_active=True).order_by("order_index", "name")
    result = []

    for subject in subjects:
        entry: dict = {
            "id": str(subject.id),
            "name": subject.name,
            "description": subject.description,
            "order_index": subject.order_index,
            "book_plan": None,
        }
        try:
            plan = subject.book_plan
            entry["book_plan"] = BookPlanSerializer(plan).data
        except Exception:
            # Subject has no BookPlan yet — return stub so UI doesn't break
            entry["book_plan"] = {
                "generation_status": "not_started",
                "topics_planned": 0,
                "topics_completed": 0,
                "avg_quality_score": 0.0,
                "completion_pct": 0.0,
            }

        result.append(entry)

    logger.info("book_subjects_listed", count=len(result))
    return Response(result, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/book/tree/{subject_id}/
# ─────────────────────────────────────────────────────────────────────────────


@api_view(["GET"])
@permission_classes([AllowAny])
def subject_tree(request: Request, subject_id: str) -> Response:
    """
    Returns the full subject → module → topic → subtopic hierarchy.
    Each node carries content_status and quality_score so the navbar
    can show generation progress inline (e.g. grey=empty, green=book_quality).
    Used by: hamburger/navbar UI.
    """
    subject = get_object_or_404(Subject, id=subject_id, is_active=True)

    modules = (
        Module.objects.filter(subject=subject, is_active=True)
        .prefetch_related(
            "topics__subtopics__subtopics",  # 3 depth levels
            "topics__book_content",
            "topics__subtopics__book_content",
            "topics__subtopics__subtopics__book_content",
        )
        .order_by("order_index", "name")
    )

    tree = {
        "id": str(subject.id),
        "name": subject.name,
        "modules": [],
    }

    for module in modules:
        module_node = {
            "id": str(module.id),
            "name": module.name,
            "order_index": module.order_index,
            "topics": [],
        }
        # Only top-level topics (no parent_topic) under this module
        root_topics = module.topics.filter(
            parent_topic__isnull=True, is_active=True
        ).order_by("order_index", "name")
        for topic in root_topics:
            module_node["topics"].append(_build_topic_tree(topic))

        tree["modules"].append(module_node)

    logger.info(
        "book_tree_fetched", subject_id=subject_id, modules=len(tree["modules"])
    )
    return Response(tree, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/book/graph/{subject_id}/
# ─────────────────────────────────────────────────────────────────────────────


@api_view(["GET"])
@permission_classes([AllowAny])
def subject_graph(request: Request, subject_id: str) -> Response:
    """
    Returns ALL topic nodes + edges for the D3.js Knowledge Graph UI.

    Nodes: every Topic under the subject (all depth levels).
    Edges — two kinds:
      hierarchical: parent → child links derived from parent_topic FK
      semantic:     TopicRelation records (related_to, cross_subject, etc.)

    Used by: Knowledge Graph UI (eye toggle).
    """
    subject = get_object_or_404(Subject, id=subject_id, is_active=True)

    # ── Topic nodes (knowledge_topic table) ───────────────────────────────
    topics = (
        Topic.objects.filter(subject=subject, is_active=True)
        .select_related("parent_topic", "module")
        .prefetch_related("book_content")
        .order_by("node_type", "name")
    )
    topic_nodes = list(TopicNodeSerializer(topics, many=True).data)

    # ── Synthetic Subject node (lives in knowledge_subject, not topic) ────
    # Subject and Module records are separate tables — add them as synthetic
    # graph nodes so the D3 graph shows the full 4-level hierarchy.
    subject_node = {
        "id": str(subject.id),
        "name": subject.name,
        "node_type": "subject_root",
        "content_status": "empty",
        "parent_topic_id": None,
        "quality_score": None,
        "graph_position": None,
        "order_index": 0,
        "difficulty_level": "medium",
    }

    # ── Synthetic Module nodes + subject→module edges ─────────────────────
    modules = Module.objects.filter(subject=subject, is_active=True).order_by(
        "order_index", "name"
    )
    module_nodes = []
    subject_to_module_edges = []
    module_to_topic_edges = []

    for module in modules:
        module_nodes.append(
            {
                "id": str(module.id),
                "name": module.name,
                "node_type": "module",
                "content_status": "empty",
                "parent_topic_id": None,
                "quality_score": None,
                "graph_position": None,
                "order_index": module.order_index,
                "difficulty_level": "medium",
            }
        )
        # Subject → Module
        subject_to_module_edges.append(
            {
                "source": str(subject.id),
                "target": str(module.id),
                "type": "contains",
            }
        )
        # Module → root topics (topics with no parent inside this module)
        for topic in topics:
            if topic.module_id == module.id and topic.parent_topic_id is None:
                module_to_topic_edges.append(
                    {
                        "source": str(module.id),
                        "target": str(topic.id),
                        "type": "contains",
                    }
                )

    # ── Hierarchical edges between topics (parent_topic FK) ───────────────
    topic_to_topic_edges = []
    for topic in topics:
        if topic.parent_topic_id:
            topic_to_topic_edges.append(
                {
                    "source": str(topic.parent_topic_id),
                    "target": str(topic.id),
                    "type": "contains",
                }
            )

    # ── Semantic edges (TopicRelation table) ──────────────────────────────
    topic_ids = [t.id for t in topics]
    relations = TopicRelation.objects.filter(
        source_topic_id__in=topic_ids
    ).select_related("source_topic", "target_topic")
    semantic_edges = TopicRelationSerializer(relations, many=True).data

    # ── Assemble final payload ─────────────────────────────────────────────
    all_nodes = [subject_node] + module_nodes + topic_nodes
    all_hierarchical = (
        subject_to_module_edges + module_to_topic_edges + topic_to_topic_edges
    )

    payload = {
        "subject_id": str(subject.id),
        "subject_name": subject.name,
        "nodes": all_nodes,
        "edges": {
            "hierarchical": all_hierarchical,
            "semantic": semantic_edges,
        },
    }

    logger.info(
        "book_graph_fetched",
        subject_id=subject_id,
        node_count=len(all_nodes),
        hier_edges=len(all_hierarchical),
        semantic_edges=len(semantic_edges),
    )
    return Response(payload, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/book/graph/{subject_id}/node/{topic_id}/children/
# ─────────────────────────────────────────────────────────────────────────────


@api_view(["GET"])
@permission_classes([AllowAny])
def graph_node_children(request: Request, subject_id: str, topic_id: str) -> Response:
    """
    Returns ONLY the direct children of a topic node.
    Called on single-click of a collapsed node in the Knowledge Graph.
    Lazy-load pattern — avoids sending the full graph on initial load.
    Used by: progressive disclosure in Knowledge Graph UI.
    """
    # Validate the parent exists and belongs to the claimed subject
    parent = get_object_or_404(
        Topic, id=topic_id, subject_id=subject_id, is_active=True
    )

    children = (
        Topic.objects.filter(parent_topic=parent, is_active=True)
        .prefetch_related("book_content")
        .order_by("order_index", "name")
    )
    serialized = TopicNodeSerializer(children, many=True).data

    logger.info(
        "graph_children_fetched",
        parent_id=topic_id,
        children_count=len(serialized),
    )
    return Response(serialized, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/book/content/{topic_id}/
# ─────────────────────────────────────────────────────────────────────────────


@api_view(["GET"])
@permission_classes([AllowAny])
def book_content_detail(request: Request, topic_id: str) -> Response:
    """
    Returns full BookContent for a topic node.
    Includes the full markdown article + nested cross-references.
    Used by: article reader panel in both navbar and graph UI.
    """
    content = get_object_or_404(
        BookContent.objects.select_related("topic", "subject").prefetch_related(
            "outgoing_references__target_content__topic",
        ),
        topic__id=topic_id,
    )

    logger.info(
        "book_content_fetched",
        topic_id=topic_id,
        topic_name=content.topic.name,
        quality_score=content.quality_score,
    )
    return Response(BookContentSerializer(content).data, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/book/content/{topic_id}/cross-references/
# ─────────────────────────────────────────────────────────────────────────────


@api_view(["GET"])
@permission_classes([AllowAny])
def book_content_cross_references(request: Request, topic_id: str) -> Response:
    """
    Returns all outgoing CrossReference records for an article.
    Dedicated endpoint so the See Also section can load independently
    without fetching the full article body again.
    Used by: See Also section in article reader.
    """
    # Verify topic exists first to give a clean 404
    get_object_or_404(Topic, id=topic_id, is_active=True)

    refs = (
        CrossReference.objects.filter(source_content__topic__id=topic_id)
        .select_related(
            "target_content__topic",
        )
        .order_by("ref_type")
    )
    serialized = CrossReferenceSerializer(refs, many=True).data

    logger.info(
        "cross_references_fetched",
        topic_id=topic_id,
        count=len(serialized),
    )
    return Response(serialized, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/book/generation-log/    (staff only)
# ─────────────────────────────────────────────────────────────────────────────


@api_view(["GET"])
@permission_classes([IsAdminUser])
def generation_log_list(request: Request) -> Response:
    """
    Returns recent GenerationLog records for admin monitoring.
    Supports optional ?subject= and ?status= query filters.
    Capped at 100 most recent entries — no pagination needed for admin panel.
    Requires: is_staff (IsAdminUser).
    Used by: admin monitoring dashboard.
    """
    qs = GenerationLog.objects.order_by("-created_at")

    subject_filter = request.query_params.get("subject", "").strip()
    if subject_filter:
        qs = qs.filter(subject_name__icontains=subject_filter)

    status_filter = request.query_params.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    qs = qs[:100]
    serialized = GenerationLogSerializer(qs, many=True).data

    logger.info(
        "generation_log_listed",
        count=len(serialized),
        subject_filter=subject_filter or None,
        status_filter=status_filter or None,
    )
    return Response(serialized, status=status.HTTP_200_OK)
