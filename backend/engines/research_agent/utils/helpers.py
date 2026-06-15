"""
engines/research_agent/utils/helpers.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Utility helpers shared across research_agent engine.
Implemented progressively as needed in Phases 2–9.
"""

import hashlib
import structlog

logger = structlog.get_logger(__name__)


def sha256_hash(text: str) -> str:
    """
    SHA-256 hash of normalized text.
    Used by cache_service for query deduplication (Opt #4).
    """
    normalized = text.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def truncate_text(text: str, max_chars: int = 400) -> str:
    """
    Truncate text to max_chars for output_summary storage.
    Preserves word boundaries.
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"


def safe_float(value, default: float = 0.0) -> float:
    """Safe cast to float — returns default on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
