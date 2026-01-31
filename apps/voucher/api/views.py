"""
ViewSets for the Voucher app.
"""
from rest_framework import viewsets, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Sum

from apps.api.pagination import StandardResultsSetPagination
from apps.api.permissions import IsStaffUser, IsSingletonAdmin
from apps.voucher.models import Voucher, VoucherSetting, OrderVoucher
from apps.voucher.api.serializers import (
    VoucherSerializer,
    VoucherListSerializer,
    VoucherCreateSerializer,
    BulkVoucherCreateSerializer,
    VoucherSettingSerializer,
    OrderVoucherSerializer,
)


class VoucherSettingViewSet(viewsets.ModelViewSet):
    """ViewSet for VoucherSetting model."""
    queryset = VoucherSetting.objects.all()
    serializer_class = VoucherSettingSerializer
    permission_classes = [IsAuthenticated, IsSingletonAdmin]
    pagination_class = None  # Singleton, no pagination needed

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Return the active voucher setting."""
        setting = VoucherSetting.objects.filter(active=True).first()
        if setting:
            return Response(VoucherSettingSerializer(setting).data)
        return Response(
            {'error': 'No active voucher setting found'},
            status=status.HTTP_404_NOT_FOUND
        )


class VoucherViewSet(viewsets.ModelViewSet):
    """ViewSet for Voucher model."""
    queryset = Voucher.objects.all().select_related(
        'account__participant__program'
    )
    permission_classes = [IsAuthenticated, IsStaffUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter
    ]
    filterset_fields = ['active', 'voucher_type', 'state', 'account']
    search_fields = [
        'account__participant__name',
        'account__participant__customer_number',
        'notes'
    ]
    ordering_fields = ['created_at', 'updated_at', 'state']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return VoucherListSerializer
        if self.action == 'create':
            return VoucherCreateSerializer
        if self.action == 'bulk_create':
            return BulkVoucherCreateSerializer
        return VoucherSerializer

    @action(detail=False, methods=['get'])
    def active_vouchers(self, request):
        """Return only active vouchers."""
        vouchers = self.get_queryset().filter(active=True, state='applied')
        page = self.paginate_queryset(vouchers)
        if page is not None:
            serializer = VoucherListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = VoucherListSerializer(vouchers, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_program(self, request):
        """Return voucher summary grouped by program."""
        from apps.lifeskills.models import Program
        programs = Program.objects.all()
        result = []
        for program in programs:
            vouchers = self.get_queryset().filter(
                account__participant__program=program
            )
            active_count = vouchers.filter(active=True, state='applied').count()
            total_amount = sum(
                v.voucher_amnt for v in vouchers.filter(active=True, state='applied')
            )
            result.append({
                'program_id': program.id,
                'program_name': program.name,
                'total_vouchers': vouchers.count(),
                'active_vouchers': active_count,
                'total_active_amount': total_amount,
            })
        return Response(result)

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Create vouchers in bulk for multiple accounts or a program."""
        serializer = BulkVoucherCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        created_vouchers = []
        with transaction.atomic():
            if data.get('program_id'):
                from apps.account.models import Participant
                participants = Participant.objects.filter(
                    program_id=data['program_id'],
                    active=True
                ).select_related('account_balance')
                accounts = [p.account_balance for p in participants if hasattr(p, 'account_balance')]
            else:
                from apps.account.models import AccountBalance
                accounts = AccountBalance.objects.filter(
                    id__in=data.get('account_ids', [])
                )

            for account in accounts:
                voucher = Voucher.objects.create(
                    account=account,
                    voucher_type=data.get('voucher_type', 'grocery'),
                    notes=data.get('notes', '')
                )
                created_vouchers.append(voucher)

        return Response({
            'created_count': len(created_vouchers),
            'vouchers': VoucherListSerializer(created_vouchers, many=True).data
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def apply(self, request, pk=None):
        """Apply a voucher (change state from pending to applied)."""
        voucher = self.get_object()
        if voucher.state != 'pending':
            return Response(
                {'error': f'Cannot apply voucher with state: {voucher.state}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Use queryset update to bypass editable=False restriction
        Voucher.objects.filter(pk=voucher.pk).update(state='applied')
        voucher.refresh_from_db()
        return Response(VoucherSerializer(voucher).data)

    @action(detail=True, methods=['post'])
    def expire(self, request, pk=None):
        """Expire a voucher."""
        voucher = self.get_object()
        if voucher.state == 'consumed':
            return Response(
                {'error': 'Cannot expire a consumed voucher'},
                status=status.HTTP_400_BAD_REQUEST
            )
        Voucher.objects.filter(pk=voucher.pk).update(
            state='expired', active=False
        )
        voucher.refresh_from_db()
        return Response(VoucherSerializer(voucher).data)


class OrderVoucherViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for OrderVoucher model (read-only)."""
    queryset = OrderVoucher.objects.all().select_related(
        'order', 'voucher'
    )
    serializer_class = OrderVoucherSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['order', 'voucher']
    ordering_fields = ['applied_at', 'applied_amount']
    ordering = ['-applied_at']
