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
)
from apps.log.api.serializers import (
    EmailTypeSerializer,
    EmailTypeListSerializer,
    EmailLogSerializer,
    VoucherLogSerializer,
    OrderValidationLogSerializer,
    UserLoginLogSerializer,
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

    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """Preview email with sample context."""
        email_type = self.get_object()
        context = EmailType.get_sample_context()
        return Response({
            'subject': email_type.render_subject(context),
            'html': email_type.render_html(context),
            'text': email_type.render_text(context),
        })

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
