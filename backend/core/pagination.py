"""Core Pagination Classes."""

from rest_framework.pagination import LimitOffsetPagination, PageNumberPagination
from engines.shared.services.cache_service import get_cache_service


class StandardPageNumberPagination(PageNumberPagination):
    """
    Standard PageNumberPagination enforcing 20 items per page
    for fast load times and preventing database overwhelming.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = (
        100  # P2.5 — prevent ?page_size=1000 from dumping 1000 rows in one response
    )

    def get_count(self, queryset):
        """
        Determine an object count, supporting caching to avoid expensive SELECT COUNT(*).
        """
        try:
            cache_service = get_cache_service()

            custom_key = getattr(queryset, "_custom_count_cache_key", None)
            if custom_key:
                return cache_service.get_count(custom_key, queryset)

            model_name = queryset.model._meta.db_table
            import hashlib

            query_str = str(queryset.query)
            query_hash = hashlib.md5(query_str.encode("utf-8")).hexdigest()
            cache_key = f"q_count_{model_name}_{query_hash}"

            return cache_service.get_count(cache_key, queryset)
        except Exception:
            # Fallback to standard count if cache/redis is unavailable
            return super().get_count(queryset)


class StandardLimitOffsetPagination(LimitOffsetPagination):
    """
    Standard LimitOffsetPagination for high-volume endpoints
    supporting lightweight client-side or server-side scroll tracking.
    """

    default_limit = 20
    limit_query_param = "limit"
    offset_query_param = "offset"
    max_limit = 100

    def get_count(self, queryset):
        """
        Determine an object count, supporting caching to avoid expensive SELECT COUNT(*).
        """
        try:
            from engines.shared.services.cache_service import get_cache_service

            cache_service = get_cache_service()

            custom_key = getattr(queryset, "_custom_count_cache_key", None)
            if custom_key:
                return cache_service.get_count(custom_key, queryset)

            model_name = queryset.model._meta.db_table
            import hashlib

            query_str = str(queryset.query)
            query_hash = hashlib.md5(query_str.encode("utf-8")).hexdigest()
            cache_key = f"q_count_{model_name}_{query_hash}"

            return cache_service.get_count(cache_key, queryset)
        except Exception:
            # Fallback to standard count if cache/redis is unavailable
            return super().get_count(queryset)
