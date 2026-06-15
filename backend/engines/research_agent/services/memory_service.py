"""
engines/research_agent/services/memory_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Per-user long-term memory (Redis).

Remembers a LOGGED-IN user's research interests across sessions — which domains
(polity / economy / science / ...) they research most. A future enhancement can
feed this to the Planner to tailor research; for now the orchestrator RECORDS it
after every completed session and it's queryable.

ISOLATION (Risk #49): every key is namespaced by user_id, so one user's memory
can NEVER leak into another's. Anonymous users get NO long-term memory (guests
are session-only by design).

GRACEFUL FALLBACK: Redis down → record() no-ops, get() returns empty memory.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

# Per-user memory: a Redis hash of domain → count.
_USER_MEMORY_KEY = "research:memory:user:{user_id}"
_MEMORY_TTL = 180 * 24 * 3600  # 180 days rolling


class MemoryService:
    """Module-level singleton. Per-user, Redis-backed, fail-safe."""

    def record_query(self, user_id: str | None, domain: str | None) -> None:
        """
        Record that this user researched in `domain`. Increments the user's
        per-domain counter. No-op for anonymous users or on Redis error.
        """
        if not user_id or not domain:
            return
        conn = self._redis()
        if conn is None:
            return
        try:
            key = _USER_MEMORY_KEY.format(user_id=user_id)
            conn.hincrby(key, domain, 1)
            conn.hincrby(key, "_total", 1)
            conn.expire(key, _MEMORY_TTL)
        except Exception as exc:
            logger.warning("research_agent.memory.record_error", error=str(exc))

    def get_user_memory(self, user_id: str | None) -> dict:
        """
        Return {"domains": {domain: count}, "top_domain": str|None, "total": int}.
        Empty memory if anonymous, no history, or Redis down.
        """
        empty: dict = {"domains": {}, "top_domain": None, "total": 0}
        if not user_id:
            return empty
        conn = self._redis()
        if conn is None:
            return empty
        try:
            key = _USER_MEMORY_KEY.format(user_id=user_id)
            raw = conn.hgetall(key) or {}
            domains: dict[str, int] = {}
            total = 0
            for k, v in raw.items():
                k = k.decode("utf-8") if isinstance(k, bytes) else k
                v = int(v)
                if k == "_total":
                    total = v
                else:
                    domains[k] = v
            top_domain = max(domains, key=lambda d: domains[d]) if domains else None
            return {"domains": domains, "top_domain": top_domain, "total": total}
        except Exception as exc:
            logger.warning("research_agent.memory.get_error", error=str(exc))
            return empty

    def _redis(self):
        try:
            from django_redis import get_redis_connection

            return get_redis_connection("default")
        except Exception:
            return None


# Module-level singleton.
memory_service = MemoryService()
