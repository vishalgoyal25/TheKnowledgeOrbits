"""Core Pagination Classes."""

from rest_framework.pagination import LimitOffsetPagination, PageNumberPagination


class StandardPageNumberPagination(PageNumberPagination):
    """
    Standard PageNumberPagination enforcing 20 items per page
    for fast load times and preventing database overwhelming.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class StandardLimitOffsetPagination(LimitOffsetPagination):
    """
    Standard LimitOffsetPagination for high-volume endpoints
    supporting lightweight client-side or server-side scroll tracking.
    """

    default_limit = 20
    limit_query_param = "limit"
    offset_query_param = "offset"
    max_limit = 100
