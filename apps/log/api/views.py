"""
ViewSets for the Log app.
"""
from rest_framework import viewsets, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from apps.api.pagination import StandardResultsSetPagination
from apps.api.permissions import IsStaffUser
from apps.log.models import (
    EmailType,
    EmailLog,
    VoucherLog,
    OrderValidationLog,
    UserLoginLog,
    GraceAllowanceLog,
)
from apps.log.api.serializers import (
    EmailTypeSerializer,
    EmailTypeListSerializer,
    EmailLogSerializer,
    VoucherLogSerializer,
    OrderValidationLogSerializer,
    UserLoginLogSerializer,
    GraceAllowanceLogSerializer,
)


class EmailTypeViewSet(viewsets.ModelViewSet):
    """ViewSet for EmailType model."""
    queryset = EmailType.objects.all()
    permission_classes = [IsAuthenticated, IsStaffUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'display_name', 'subject', 'description']
    ordering_fields = ['display_name', 'created_at', 'is_active']
    ordering = ['display_name']

    def get_serializer_class(self):
        if self.action == 'list':
            return EmailTypeListSerializer
        return EmailTypeSerializer

    @action(detail=True, methods=['get', 'post'])
    def preview(self, request, pk=None):
        """Render this email type with realistic sample data.

        GET  ?language=en|es      — render the saved content.
        POST {subject?, html_content?, text_content?, language?}
                                  — render draft content without saving;
                                    omitted fields fall back to saved values.

        Returns {subject, html, text, language}. A template syntax error
        returns 400 with {detail, field} naming the offending field.
        """
        from django.template import Context, Template, TemplateSyntaxError
        from django.utils import translation

        email_type = self.get_object()
        data = request.data if request.method == 'POST' else request.query_params
        language = data.get('language') or 'en'
        if language not in ('en', 'es'):
            return Response(
                {'detail': f"Unsupported language '{language}'.", 'field': 'language'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        context = email_type.get_sample_context_for_type()
        rendered = {}
        with translation.override(language):
            drafts = {
                'subject': request.data.get('subject') if request.method == 'POST' else None,
                'html': request.data.get('html_content') if request.method == 'POST' else None,
                'text': request.data.get('text_content') if request.method == 'POST' else None,
            }
            saved_renderers = {
                'subject': lambda: email_type.render_subject(context),
                'html': lambda: email_type.render_html(context),
                'text': lambda: email_type.render_text(context),
            }
            for key in ('subject', 'html', 'text'):
                try:
                    if drafts[key] is not None:
                        rendered[key] = Template(drafts[key]).render(Context(context))
                    else:
                        rendered[key] = saved_renderers[key]()
                except TemplateSyntaxError as exc:
                    field = 'subject' if key == 'subject' else f'{key}_content'
                    return Response(
                        {'detail': str(exc), 'field': field},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        rendered['language'] = language
        return Response(rendered)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Return only active email types."""
        email_types = self.get_queryset().filter(is_active=True)
        serializer = EmailTypeListSerializer(email_types, many=True)
        return Response(serializer.data)


class EmailLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for EmailLog model (read-only)."""
    queryset = EmailLog.objects.all().select_related('user', 'email_type')
    serializer_class = EmailLogSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter
    ]
    filterset_fields = ['user', 'email_type', 'status']
    search_fields = ['subject', 'user__email']
    ordering_fields = ['sent_at', 'status']
    ordering = ['-sent_at']


class VoucherLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for VoucherLog model (read-only)."""
    queryset = VoucherLog.objects.all().select_related(
        'participant', 'user', 'order', 'voucher'
    )
    serializer_class = VoucherLogSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter
    ]
    filterset_fields = ['participant', 'voucher', 'order', 'log_type']
    search_fields = ['message']
    ordering_fields = ['created_at', 'validated_at']
    ordering = ['-created_at']


class OrderValidationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for OrderValidationLog model (read-only)."""
    queryset = OrderValidationLog.objects.all().select_related(
        'participant', 'user', 'order', 'product'
    )
    serializer_class = OrderValidationLogSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter
    ]
    filterset_fields = ['participant', 'order', 'product', 'log_type']
    search_fields = ['message']
    ordering_fields = ['created_at', 'validated_at']
    ordering = ['-created_at']


class UserLoginLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for UserLoginLog model (read-only)."""
    queryset = UserLoginLog.objects.all().select_related('user', 'participant')
    serializer_class = UserLoginLogSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter
    ]
    filterset_fields = ['user', 'action', 'participant']
    search_fields = ['username_attempted', 'user__username', 'ip_address']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']

    @action(detail=False, methods=['get'])
    def failed_logins(self, request):
        """Return failed login attempts."""
        logs = self.get_queryset().filter(action='failed_login')
        page = self.paginate_queryset(logs)
        if page is not None:
            serializer = UserLoginLogSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = UserLoginLogSerializer(logs, many=True)
        return Response(serializer.data)


class GraceAllowanceLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for GraceAllowanceLog model (read-only)."""
    queryset = GraceAllowanceLog.objects.all().select_related(
        'participant', 'order'
    )
    serializer_class = GraceAllowanceLogSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter
    ]
    filterset_fields = ['participant', 'order', 'proceeded']
    search_fields = ['participant__name', 'participant__customer_number']
    ordering_fields = ['created_at', 'amount_over']
    ordering = ['-created_at']
