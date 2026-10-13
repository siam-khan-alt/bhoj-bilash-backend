"""List endpoints are ALWAYS paginated — response cost O(page), never O(table)."""

from rest_framework.pagination import PageNumberPagination


class BhojBilashPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
