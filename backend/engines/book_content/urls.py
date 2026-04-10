"""
Book Content Engine — URL Configuration
Registered in core/urls.py as: path("api/v1/book/", include("engines.book_content.urls"))

Endpoints:
  GET  subjects/                                    → subject_list
  GET  tree/<uuid:subject_id>/                      → subject_tree
  GET  graph/<uuid:subject_id>/                     → subject_graph
  GET  graph/<uuid:subject_id>/node/<uuid:topic_id>/children/  → graph_node_children
  GET  content/<uuid:topic_id>/                     → book_content_detail
  GET  content/<uuid:topic_id>/cross-references/    → book_content_cross_references
  GET  generation-log/                              → generation_log_list  (staff only)
  POST internal/generate/<uuid:topic_id>/           → internal_generate   (internal only)
"""

from django.urls import path

from engines.book_content.views import (
    book_content_cross_references,
    book_content_detail,
    generation_log_list,
    graph_node_children,
    internal_generate,
    subject_graph,
    subject_list,
    subject_tree,
)

app_name = "book_content"

urlpatterns = [
    # Subject selector
    path(
        "subjects/",
        subject_list,
        name="subject-list",
    ),
    # Navbar / hamburger tree
    path(
        "tree/<uuid:subject_id>/",
        subject_tree,
        name="subject-tree",
    ),
    # Knowledge Graph — full graph
    path(
        "graph/<uuid:subject_id>/",
        subject_graph,
        name="subject-graph",
    ),
    # Knowledge Graph — lazy-load children
    path(
        "graph/<uuid:subject_id>/node/<uuid:topic_id>/children/",
        graph_node_children,
        name="graph-node-children",
    ),
    # Article reader — full content
    path(
        "content/<uuid:topic_id>/",
        book_content_detail,
        name="book-content-detail",
    ),
    # Article reader — See Also section
    path(
        "content/<uuid:topic_id>/cross-references/",
        book_content_cross_references,
        name="book-content-cross-references",
    ),
    # Admin monitoring (staff only)
    path(
        "generation-log/",
        generation_log_list,
        name="generation-log-list",
    ),
    # Internal: trigger background static generation (called by daily_ca engine only)
    path(
        "internal/generate/<uuid:topic_id>/",
        internal_generate,
        name="internal-generate",
    ),
]
