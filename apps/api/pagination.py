from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for API endpoints compatible with react-admin."""
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        """
        Return paginated response with headers for react-admin.
        react-admin expects Content-Range header for pagination.
        """
        response = super().get_paginated_response(data)
        response['Content-Range'] = f'{self.page.start_index()}-{self.page.end_index()}/{self.page.paginator.count}'
        response['Access-Control-Expose-Headers'] = 'Content-Range'
        return response
