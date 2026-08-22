from rest_framework.pagination import CursorPagination, PageNumberPagination


class StandardPageNumberPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class CheckResultCursorPagination(CursorPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-checked_at"
    cursor_query_param = "cursor"
