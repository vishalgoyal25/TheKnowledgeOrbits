"""
engines/book_content/constants.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dependency-free constants for the book_content engine.

Lives at the engine ROOT (not under services/) on purpose: importing anything
from book_content.services runs services/__init__.py, which eagerly loads the
LLM stack (ingestor → book_planner → llm_service → cerebras SDK). Modules that
only need a shared retrieval constant — e.g. knowledge.search_service — must be
able to read it WITHOUT dragging in that LLM stack, so lean environments (the
zero-LLM current_affairs scraper on GitHub Actions) can still boot the URLconf.

Keep this module free of heavy / optional imports.
"""

# Cosine-distance noise floor for RAG retrieval relevance.
# Single source of truth: retrieval_service (the RAG gateway) and
# knowledge.search_service both import this value so the search UI and
# generation-grounding can never silently drift apart.
# 0.62 distance ⇔ 0.38 cosine similarity (permissive recall floor).
GROUNDING_DISTANCE_THRESHOLD: float = 0.62

# Redis keys for the per-subject tree and graph payloads. ONE definition: the
# views read them, signals.py busts them, tests assert them. The version
# suffix changes whenever the payload shape changes, so a stale entry from an
# older deploy can never be served (v2 = nodes carry `slug`, G3.10).
SUBJECT_CACHE_VERSION = "v2"


def subject_tree_cache_key(subject_id: str) -> str:
    return f"book_subject_tree_{subject_id}_{SUBJECT_CACHE_VERSION}"


def subject_graph_cache_key(subject_id: str) -> str:
    return f"book_subject_graph_{subject_id}_{SUBJECT_CACHE_VERSION}"
