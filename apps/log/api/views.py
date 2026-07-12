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

    @action(detail=True, methods=['post'], url_path='send-test')
    def send_test(self, request, pk=None):
        """Send a rendered draft of this email to the requesting staff user.

        Body: {subject?, html_content?, text_content?, language?} — same
        draft semantics as POST preview. The send is synchronous, goes to
        request.user.email, and is logged as EmailLog(is_test=True) so it
        never interferes with dedup or DLQ retries.
        """
        from django.template import Context, Template, TemplateSyntaxError
        from django.utils import translation

        from apps.account.tasks.email import (
            create_email_log,
            get_email_settings,
            send_email_message,
        )

        if not request.user.email:
            return Response(
                {'detail': 'Your account has no email address to send the test to.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email_type = self.get_object()
        language = request.data.get('language') or 'en'
        if language not in ('en', 'es'):
            return Response(
                {'detail': f"Unsupported language '{language}'.", 'field': 'language'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        context = email_type.get_sample_context_for_type()
        # Test sends render with the requesting user's real details (name,
        # username, email) instead of the sample participant, so the email
        # you receive reads as it would for you.
        context['user'] = request.user
        with translation.override(language):
            try:
                subject_draft = request.data.get('subject')
                html_draft = request.data.get('html_content')
                text_draft = request.data.get('text_content')
                subject = (
                    Template(subject_draft).render(Context(context))
                    if subject_draft is not None
                    else email_type.render_subject(context)
                )
                html = (
                    Template(html_draft).render(Context(context))
                    if html_draft is not None
                    else email_type.render_html(context)
                )
                text = (
                    Template(text_draft).render(Context(context))
                    if text_draft is not None
                    else email_type.render_text(context)
                )
            except TemplateSyntaxError as exc:
                return Response(
                    {'detail': str(exc)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        email_settings = get_email_settings()
        from_email = email_type.from_email or email_settings.get_from_email()
        reply_to = email_type.reply_to or email_settings.get_reply_to()
        subject = f"[TEST] {subject}"

        try:
            message_id = send_email_message(
                subject, html, text or html, request.user.email,
                from_email=from_email, reply_to=reply_to,
            )
        except Exception as exc:
            return Response(
                {'detail': f'Send failed: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        create_email_log(
            request.user, email_type, subject, message_id=message_id,
            is_test=True,
        )

        return Response({
            'detail': f'Test email sent to {request.user.email}',
            'message_id': message_id,
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
    filterset_fields = ['user', 'email_type', 'status', 'is_test']
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
