"""
engines/research_agent/services/cache_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Redis-backed query-result cache (Opt #4).

An IDENTICAL question (same query_hash) returns the previously-generated report
INSTANTLY (<1s, zero LLM tokens) instead of re-running all 8 agents. This is the
single biggest cost/latency win and directly relieves the LLM quota pressure.

Flow:
  query_view  → cache_service.get(query_hash)  → HIT → return report immediately
  orchestrator→ cache_service.set(query_hash, report) after a good run

GRACEFUL FALLBACK (Risk #19): if Redis is down, get() returns None (cache miss →
pipeline runs normally) and set() no-ops. The cache NEVER raises.
"""

from __future__ import annotations

import json

import structlog

from engines.research_agent.constants import QUERY_CACHE_TTL, QUERY_HASH_PREFIX

logger = structlog.get_logger(__name__)

# Cache key: ra:query:{sha256}
_CACHE_KEY = QUERY_HASH_PREFIX + "{query_hash}"


class CacheService:
    """Module-level singleton. All state in Redis; fails safe."""

    def get(self, query_hash: str) -> dict | None:
        """Return the cached report dict for this query_hash, or None on miss/error."""
        conn = self._redis()
        if conn is None:
            return None
        try:
            raw = conn.get(_CACHE_KEY.format(query_hash=query_hash))
            if not raw:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            logger.info("research_agent.cache.hit", query_hash=query_hash[:12])
            return json.loads(raw)
        except Exception as exc:
            logger.warning("research_agent.cache.get_error", error=str(exc))
            return None

    def set(self, query_hash: str, report: dict, ttl: int = QUERY_CACHE_TTL) -> None:
        """Cache a report dict under query_hash with a TTL. No-op on error."""
        conn = self._redis()
        if conn is None:
            return
        try:
            conn.set(
                _CACHE_KEY.format(query_hash=query_hash),
                json.dumps(report, default=str),
                ex=ttl,
            )
            logger.info("research_agent.cache.set", query_hash=query_hash[:12])
        except Exception as exc:
            logger.warning("research_agent.cache.set_error", error=str(exc))

    def invalidate(self, query_hash: str) -> None:
        """Drop a cached entry (e.g. if a report is found to be stale/wrong)."""
        conn = self._redis()
        if conn is None:
            return
        try:
            conn.delete(_CACHE_KEY.format(query_hash=query_hash))
        except Exception:
            pass

    def patch_confidence(self, query_hash: str, confidence_score: float) -> None:
        """
        Write-back the composite confidence into an already-cached report.

        DeepEval finishes ~seconds AFTER the report is cached, so the cached blob
        is stored with `confidence_score: None`. Once the score exists, we patch
        it in so every FUTURE cache hit serves a complete report (cache stays
        coherent with ra_report — the system of record).

        Safe by design: no-op if Redis is down or the entry already expired (a
        miss just means a future run re-evaluates). Preserves the remaining TTL
        so back-filling never extends the cache lifetime. NEVER raises.
        """
        conn = self._redis()
        if conn is None:
            return
        try:
            key = _CACHE_KEY.format(query_hash=query_hash)
            raw = conn.get(key)
            if not raw:
                return  # entry expired or was never cached — nothing to patch
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            report = json.loads(raw)
            report["confidence_score"] = confidence_score

            # Preserve the remaining TTL. ttl() returns -1 (no expiry) or -2
            # (missing) — in either edge case fall back to the default window.
            ttl = conn.ttl(key)
            ex = ttl if isinstance(ttl, int) and ttl > 0 else QUERY_CACHE_TTL
            conn.set(key, json.dumps(report, default=str), ex=ex)
            logger.info(
                "research_agent.cache.confidence_patched",
                query_hash=query_hash[:12],
                confidence=confidence_score,
            )
        except Exception as exc:
            logger.warning("research_agent.cache.patch_error", error=str(exc))

    def _redis(self):
        try:
            from django_redis import get_redis_connection

            return get_redis_connection("default")
        except Exception:
            return None


# Module-level singleton.
cache_service = CacheService()
