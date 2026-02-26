"""Core Pagination Classes."""

from rest_framework.pagination import PageNumberPagination


class StandardPageNumberPagination(PageNumberPagination):
    """
    Standard PageNumberPagination enforcing 20 items per page
    for fast load times and preventing database overwhelming.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
