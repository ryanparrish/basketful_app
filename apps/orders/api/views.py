"""
ViewSets for the Orders app.
"""
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Sum, Q
from django.core.exceptions import ValidationError
from django.core.cache import cache

from apps.api.pagination import StandardResultsSetPagination
from apps.api.permissions import IsAdminOrReadOnly, IsStaffUser, IsOwnerOrAdmin
from apps.orders.models import (
    Order,
    OrderItem,
    FailedOrderAttempt,
    CombinedOrder,
    PackingSplitRule,
    PackingList,
)
from apps.log.models import OrderValidationLog
from apps.orders.api.serializers import (
    OrderSerializer,
    OrderListSerializer,
    OrderCreateSerializer,
    OrderItemSerializer,
    OrderItemCreateSerializer,
    OrderValidationLogSerializer,
    FailedOrderAttemptSerializer,
    CombinedOrderSerializer,
    CombinedOrderListSerializer,
    PackingSplitRuleSerializer,
    PackingListSerializer,
)
from apps.orders.api.throttles import OrderSubmissionThrottle
from core.models import ProgramSettings


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

    def get_throttles(self):
        """Apply throttling only to create action."""
        if self.action == 'create':
            return [OrderSubmissionThrottle()]
        return super().get_throttles()

    def create(self, request, *args, **kwargs):
        """
        Create order with throttling, idempotency, and comprehensive error logging.
        """
        # Extract metadata for audit
        ip_address = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        
        # Add metadata to serializer context
        request_meta = {
            'ip': ip_address,
            'user_agent': user_agent,
        }
        
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request, 'request_meta': request_meta}
        )
        serializer.is_valid(raise_exception=True)
        
        try:
            # The serializer's create method will call OrderOrchestration.create_order
            # which now handles idempotency, distributed lock, and validation
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED,
                headers=headers
            )
        except ValidationError as e:
            # Validation errors are already logged by OrderOrchestration.create_order
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def get_client_ip(self, request):
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

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

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def validate_cart(self, request):
        """
        Validate cart items against business rules without creating an order.
        Backend is the source of truth for all validation logic.
        
        Request body:
        {
            "participant_id": 123,
            "items": [
                {"product_id": 1, "quantity": 2},
                {"product_id": 2, "quantity": 1}
            ]
        }
        
        Response:
        {
            "valid": true/false,
            "violations": [
                {
                    "type": "balance" | "limit" | "window" | "voucher",
                    "severity": "error" | "warning",
                    "message": "Human-readable message",
                    "amount_over": 5.00,
                    "grace_allowed": true/false
                }
            ],
            "balances": {
                "available": "40.00",
                "hygiene": "13.33",
                "go_fresh": "20.00"
            },
            "limits": [
                {
                    "category_name": "Meat",
                    "used": 3,
                    "max": 4,
                    "scope": "per_adult",
                    "per_household_max": 8
                }
            ],
            "rules_version": "abc123..."
        }
        """
        from apps.account.models import Participant, AccountBalance
        from apps.pantry.models import Product, ProductLimit
        from apps.orders.utils.validators import CategoryLimitValidator
        
        # Get request data
        participant_id = request.data.get('participant_id')
        items_data = request.data.get('items', [])
        
        if not participant_id:
            return Response(
                {'error': 'participant_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get participant and account
        try:
            participant = Participant.objects.select_related(
                'accountbalance'
            ).get(id=participant_id)
            account = participant.accountbalance
        except Participant.DoesNotExist:
            return Response(
                {'error': f'Participant {participant_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except AccountBalance.DoesNotExist:
            return Response(
                {'error': f'AccountBalance not found for participant {participant_id}'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get program settings for grace allowance
        program_settings = ProgramSettings.get_settings()
        
        # Create temporary order and items (not saved to DB)
        temp_order = Order(
            account=account,
            user=request.user,
            status='confirmed'  # Set to confirmed to trigger validation
        )
        
        # We need to save the order first to add items
        temp_order.save()
        
        temp_items = []
        total_price = Decimal('0.00')
        
        try:
            for item_data in items_data:
                product_id = item_data.get('product_id')
                quantity = item_data.get('quantity', 1)
                
                try:
                    product = Product.objects.get(id=product_id)
                    item = OrderItem.objects.create(
                        order=temp_order,
                        product=product,
                        quantity=quantity,
                        price=product.price
                    )
                    temp_items.append(item)
                    total_price += item.total_price()
                except Product.DoesNotExist:
                    temp_order.delete()  # Clean up
                    return Response(
                        {'error': f'Product {product_id} not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            
            # Now run validation
            violations = []
            
            # Separate items by category
            food_items = []
            hygiene_items = []
            go_fresh_items = []
            
            for item in temp_items:
                category_name = item.product.category.name.lower() if item.product.category else ''
                if category_name == 'hygiene':
                    hygiene_items.append(item)
                elif category_name == 'go fresh':
                    go_fresh_items.append(item)
                else:
                    food_items.append(item)
            
            # Calculate totals
            food_total = sum(item.total_price() for item in food_items)
            hygiene_total = sum(item.total_price() for item in hygiene_items)
            go_fresh_total = sum(item.total_price() for item in go_fresh_items)
            
            # Get balances
            available_balance = account.available_balance
            hygiene_balance = account.hygiene_balance
            go_fresh_balance = account.go_fresh_balance
            
            # Validate available balance (food items)
            if food_total > available_balance:
                amount_over = float(food_total - available_balance)
                grace_allowed = (
                    program_settings.grace_enabled and 
                    amount_over <= float(program_settings.grace_amount)
                )
                violations.append({
                    'type': 'balance',
                    'severity': 'warning' if grace_allowed else 'error',
                    'message': program_settings.grace_message if grace_allowed else f'Food balance exceeded by ${amount_over:.2f}',
                    'amount_over': amount_over,
                    'grace_allowed': grace_allowed
                })
            
            # Validate hygiene balance
            if hygiene_total > hygiene_balance:
                amount_over = float(hygiene_total - hygiene_balance)
                grace_allowed = (
                    program_settings.grace_enabled and 
                    amount_over <= float(program_settings.grace_amount)
                )
                violations.append({
                    'type': 'balance',
                    'severity': 'warning' if grace_allowed else 'error',
                    'message': program_settings.grace_message if grace_allowed else f'Hygiene balance exceeded by ${amount_over:.2f}',
                    'amount_over': amount_over,
                    'grace_allowed': grace_allowed
                })
            
            # Validate Go Fresh balance
            if go_fresh_balance > 0 and go_fresh_total > go_fresh_balance:
                amount_over = float(go_fresh_total - go_fresh_balance)
                grace_allowed = (
                    program_settings.grace_enabled and 
                    amount_over <= float(program_settings.grace_amount)
                )
                violations.append({
                    'type': 'balance',
                    'severity': 'warning' if grace_allowed else 'error',
                    'message': program_settings.grace_message if grace_allowed else f'Go Fresh balance exceeded by ${amount_over:.2f}',
                    'amount_over': amount_over,
                    'grace_allowed': grace_allowed
                })
            
            # Validate category limits
            try:
                CategoryLimitValidator.validate_category_limits(temp_items, participant)
            except ValidationError as e:
                error_messages = e.error_list if hasattr(e, 'error_list') else [str(e)]
                for msg in error_messages:
                    violations.append({
                        'type': 'limit',
                        'severity': 'error',
                        'message': str(msg),
                        'amount_over': 0,
                        'grace_allowed': False
                    })
            
            # Build limits summary
            limits = []
            from collections import defaultdict
            category_counts = defaultdict(int)
            
            for item in temp_items:
                if item.product.category:
                    category_counts[item.product.category.id] += item.quantity
            
            # Get product limits
            product_limits = ProductLimit.objects.filter(
                Q(category__id__in=category_counts.keys()) |
                Q(subcategory__category__id__in=category_counts.keys())
            ).select_related('category', 'subcategory')
            
            household_size = participant.adults + participant.children + participant.infants
            
            for limit in product_limits:
                category = limit.category or limit.subcategory.category
                used = category_counts.get(category.id, 0)
                
                # Calculate max based on scope
                if limit.limit_scope == 'per_adult':
                    max_allowed = limit.limit * participant.adults
                elif limit.limit_scope == 'per_child':
                    max_allowed = limit.limit * participant.children
                elif limit.limit_scope == 'per_infant':
                    max_allowed = limit.limit * participant.infants
                elif limit.limit_scope == 'per_household':
                    max_allowed = limit.limit * household_size
                else:  # per_order
                    max_allowed = limit.limit
                
                limits.append({
                    'category_name': limit.name or category.name,
                    'used': used,
                    'max': limit.limit,
                    'scope': limit.limit_scope,
                    'per_household_max': max_allowed
                })
            
            # Check if cart is valid (no error severity violations)
            has_blocking_violations = any(v['severity'] == 'error' for v in violations)
            
            # Get rules version from Redis
            rules_version = cache.get('rules_version', 'unknown')
            
            response_data = {
                'valid': not has_blocking_violations,
                'violations': violations,
                'balances': {
                    'available': str(available_balance),
                    'hygiene': str(hygiene_balance),
                    'go_fresh': str(go_fresh_balance)
                },
                'limits': limits,
                'rules_version': rules_version
            }
            
            return Response(response_data)
            
        finally:
            # Clean up temp order and items
            temp_order.delete()

    @action(
        detail=False, 
        methods=['get'], 
        permission_classes=[IsAuthenticated, IsStaffUser],
        url_path='failure-analytics'
    )
    def failure_analytics(self, request):
        """
        Get comprehensive failure analytics for order submissions.
        
        Query params:
        - days: Number of days to analyze (default: 7, max: 90)
        - participant_id: Filter by specific participant
        
        Returns:
        - total_failures: Total failed attempts
        - failure_rate: Percentage of failures vs successes
        - common_errors: Top error types with counts
        - by_day: Daily breakdown of failures
        - top_participants: Participants with most failures
        - balance_issues: Count of balance-related failures
        """
        days = min(int(request.query_params.get('days', 7)), 90)
        participant_id = request.query_params.get('participant_id')
        
        since = timezone.now() - timedelta(days=days)
        
        # Base queryset
        failures_qs = FailedOrderAttempt.objects.filter(created_at__gte=since)
        if participant_id:
            failures_qs = failures_qs.filter(participant_id=participant_id)
        
        # Total failures
        total_failures = failures_qs.count()
        
        # Calculate failure rate (failures vs total orders)
        total_orders = Order.objects.filter(order_date__gte=since).count()
        failure_rate = (
            (total_failures / (total_failures + total_orders) * 100)
            if (total_failures + total_orders) > 0
            else 0
        )
        
        # Common error types
        from collections import Counter
        error_counter = Counter()
        
        for failure in failures_qs.only('error_summary'):
            # Extract error type from summary
            error = failure.error_summary or 'Unknown error'
            # Take first 100 chars as error type
            error_type = error[:100]
            error_counter[error_type] += 1
        
        common_errors = [
            {'error': err, 'count': count}
            for err, count in error_counter.most_common(10)
        ]
        
        # Failures by day
        from django.db.models.functions import TruncDate
        by_day = list(
            failures_qs
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )
        
        # Top participants with failures
        top_participants = list(
            failures_qs
            .values('participant__name', 'participant_id')
            .annotate(failure_count=Count('id'))
            .order_by('-failure_count')[:10]
        )
        
        # Balance-related failures
        balance_failures = failures_qs.filter(
            Q(error_summary__icontains='balance') |
            Q(error_summary__icontains='exceeded')
        ).count()
        
        return Response({
            'period': {
                'days': days,
                'since': since.isoformat(),
                'until': timezone.now().isoformat(),
            },
            'summary': {
                'total_failures': total_failures,
                'total_orders': total_orders,
                'failure_rate': round(failure_rate, 2),
                'balance_related': balance_failures,
            },
            'common_errors': common_errors,
            'by_day': by_day,
            'top_participants': top_participants,
        })

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated, IsStaffUser],
        url_path='recent-failures'
    )
    def recent_failures(self, request):
        """
        Get recent failed order attempts with full details.
        
        Query params:
        - limit: Number of records (default: 50, max: 200)
        - participant_id: Filter by participant
        """
        limit = min(int(request.query_params.get('limit', 50)), 200)
        participant_id = request.query_params.get('participant_id')
        
        qs = FailedOrderAttempt.objects.select_related(
            'participant', 'user'
        ).order_by('-created_at')
        
        if participant_id:
            qs = qs.filter(participant_id=participant_id)
        
        failures = qs[:limit]
        serializer = FailedOrderAttemptSerializer(failures, many=True)
        
        return Response({
            'count': len(failures),
            'limit': limit,
            'results': serializer.data
        })


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
