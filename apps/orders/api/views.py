"""
ViewSets for the Orders app.
"""
from rest_framework import viewsets, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Sum, Q

from apps.api.pagination import StandardResultsSetPagination
from apps.api.permissions import IsAdminOrReadOnly, IsStaffUser, IsOwnerOrAdmin
from apps.orders.models import (
    Order,
    OrderItem,
    OrderValidationLog,
    CombinedOrder,
    PackingSplitRule,
    PackingList,
)
from apps.orders.api.serializers import (
    OrderSerializer,
    OrderListSerializer,
    OrderCreateSerializer,
    OrderItemSerializer,
    OrderItemCreateSerializer,
    OrderValidationLogSerializer,
    CombinedOrderSerializer,
    CombinedOrderListSerializer,
    PackingSplitRuleSerializer,
    PackingListSerializer,
)


class OrderViewSet(viewsets.ModelViewSet):
    """ViewSet for Order model."""
    queryset = Order.objects.all().select_related(
        'account__participant__program', 'user'
    ).prefetch_related('items__product__category', 'validation_logs')
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter
    ]
    filterset_fields = ['status', 'paid', 'account', 'user']
    search_fields = [
        'order_number',
        'account__participant__name',
        'account__participant__customer_number'
    ]
    ordering_fields = ['order_date', 'status', 'created_at']
    ordering = ['-order_date']

    def get_serializer_class(self):
        if self.action == 'list':
            return OrderListSerializer
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    def get_queryset(self):
        """Filter orders based on user permissions."""
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_staff:
            # Non-staff users can only see their own orders
            qs = qs.filter(user=user)
        return qs

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm an order."""
        order = self.get_object()
        try:
            order.confirm()
            return Response(OrderSerializer(order).data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel an order."""
        order = self.get_object()
        if order.status in ['completed', 'cancelled']:
            return Response(
                {'error': f'Cannot cancel order with status: {order.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        order.status = 'cancelled'
        order.save(update_fields=['status', 'updated_at'])
        return Response(OrderSerializer(order).data)

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Return only pending orders."""
        orders = self.get_queryset().filter(status='pending')
        page = self.paginate_queryset(orders)
        if page is not None:
            serializer = OrderListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = OrderListSerializer(orders, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_program(self, request):
        """Return orders grouped by program."""
        from apps.lifeskills.models import Program
        programs = Program.objects.all()
        result = []
        for program in programs:
            orders = self.get_queryset().filter(
                account__participant__program=program
            )
            result.append({
                'program_id': program.id,
                'program_name': program.name,
                'order_count': orders.count(),
                'orders': OrderListSerializer(orders[:10], many=True).data
            })
        return Response(result)


class OrderItemViewSet(viewsets.ModelViewSet):
    """ViewSet for OrderItem model."""
    queryset = OrderItem.objects.all().select_related(
        'order', 'product__category'
    )
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['order', 'product']
    ordering_fields = ['quantity', 'price', 'created_at']
    ordering = ['created_at']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return OrderItemCreateSerializer
        return OrderItemSerializer

    def get_queryset(self):
        """Filter items based on user permissions."""
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_staff:
            qs = qs.filter(order__user=user)
        return qs


class OrderValidationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for OrderValidationLog model (read-only)."""
    queryset = OrderValidationLog.objects.all().select_related('order')
    serializer_class = OrderValidationLogSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['order']
    ordering_fields = ['created_at']
    ordering = ['-created_at']


class CombinedOrderViewSet(viewsets.ModelViewSet):
    """ViewSet for CombinedOrder model."""
    queryset = CombinedOrder.objects.all().select_related(
        'program'
    ).prefetch_related('orders', 'packing_lists__packer')
    permission_classes = [IsAuthenticated, IsStaffUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter
    ]
    filterset_fields = ['program', 'split_strategy', 'week', 'year']
    search_fields = ['name', 'program__name']
    ordering_fields = ['created_at', 'week', 'year']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return CombinedOrderListSerializer
        return CombinedOrderSerializer

    @action(detail=True, methods=['get'])
    def summarized_items(self, request, pk=None):
        """Return summarized items by category for this combined order."""
        combined_order = self.get_object()
        return Response(combined_order.summarized_items_by_category())

    @action(detail=True, methods=['post'])
    def add_orders(self, request, pk=None):
        """Add orders to this combined order."""
        combined_order = self.get_object()
        order_ids = request.data.get('order_ids', [])
        orders = Order.objects.filter(id__in=order_ids)
        combined_order.orders.add(*orders)
        return Response(CombinedOrderSerializer(combined_order).data)

    @action(detail=True, methods=['post'])
    def remove_orders(self, request, pk=None):
        """Remove orders from this combined order."""
        combined_order = self.get_object()
        order_ids = request.data.get('order_ids', [])
        orders = Order.objects.filter(id__in=order_ids)
        combined_order.orders.remove(*orders)
        return Response(CombinedOrderSerializer(combined_order).data)


class PackingSplitRuleViewSet(viewsets.ModelViewSet):
    """ViewSet for PackingSplitRule model."""
    queryset = PackingSplitRule.objects.all().select_related(
        'program', 'packer'
    ).prefetch_related('categories', 'subcategories')
    serializer_class = PackingSplitRuleSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['program', 'packer']
    ordering_fields = ['created_at']
    ordering = ['program__name', 'packer__name']


class PackingListViewSet(viewsets.ModelViewSet):
    """ViewSet for PackingList model."""
    queryset = PackingList.objects.all().select_related(
        'combined_order__program', 'packer'
    ).prefetch_related('orders', 'categories')
    serializer_class = PackingListSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['combined_order', 'packer']
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    @action(detail=True, methods=['get'])
    def summarized_items(self, request, pk=None):
        """Return summarized items for this packing list."""
        packing_list = self.get_object()
        return Response(packing_list.calculate_summarized_data())
