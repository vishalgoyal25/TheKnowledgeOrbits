from rest_framework.pagination import CursorPagination

class ContentCursorPagination(CursorPagination):
    """
    Standard pagination for Content Engine.
    Default ordering: -created_at
    """
    ordering = '-created_at'
    page_size = 20

class ChunkCursorPagination(CursorPagination):
    """
    Pagination specifically for Chunks.
    Ordering: document, chunk_index
    """
    ordering = ('document', 'chunk_index')
    page_size = 20
