"""
Shared Cache / Stats Service
Handles atomic Redis counters and high-performance caching.
"""

from typing import Any

from django.conf import settings
from django.core.cache import cache

import structlog

logger = structlog.get_logger(__name__)


class CacheService:
    """Service for advanced Redis operations."""

    @staticmethod
    def is_testing() -> bool:
        """Check if we are in a testing environment."""
        import sys

        return (
            getattr(settings, "TESTING", False)
            or "pytest" in sys.modules
            or "test" in sys.argv
        )

    @staticmethod
    def get(key: str) -> Any:
        """Get a value from cache. Bypassed in tests."""
        if CacheService.is_testing():
            return None
        return cache.get(key)

    @staticmethod
    def set(key: str, value: Any, timeout: int = 300) -> None:
        """Set a value in cache. Bypassed in tests."""
        if CacheService.is_testing():
            return
        cache.set(key, value, timeout)

    @staticmethod
    def get_count(key: str, fallback_queryset: Any = None) -> int:
        """
        Get count from cache. If not found, fetch from fallback_queryset and cache it.
        """
        if CacheService.is_testing():
            return fallback_queryset.count() if fallback_queryset is not None else 0

        count = cache.get(key)
        if count is None:
            if fallback_queryset is not None:
                count = fallback_queryset.count()
                cache.set(key, count, 3600)  # Cache for 1 hour
                logger.debug("count_cache_miss_populated", key=key, count=count)
            else:
                return 0
        return int(count)

    @staticmethod
    def increment_count(key: str) -> None:
        """Atomically increment a counter in Redis (or LocMemCache)."""
        try:
            cache.incr(key)
        except (ValueError, TypeError):
            # Handle if key doesn't exist or backend doesn't support atomic incr
            pass

    @staticmethod
    def decrement_count(key: str) -> None:
        """Atomically decrement a counter in Redis."""
        try:
            cache.decr(key)
        except (ValueError, TypeError):
            # Handle if key doesn't exist
            pass

    @staticmethod
    def invalidate_user_dashboard(user_id: str) -> None:
        """Invalidate all dashboard components for a user."""
        keys = [
            f"dashboard_{user_id}",
            f"weekly_stats_{user_id}",
            f"monthly_stats_{user_id}",
        ]
        for key in keys:
            cache.delete(key)
        logger.debug("user_dashboard_invalidated", user_id=user_id)


_cache_service = None


def get_cache_service() -> CacheService:
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service
    return _cache_service
