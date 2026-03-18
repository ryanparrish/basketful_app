"""
ViewSets for the Orders app.
"""
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from rest_framework import viewsets, filters, status, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
import io
import zipfile
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Sum, Q
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.db import IntegrityError

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
    ).prefetch_related('items__product__category', 'ordervalidationlog_set')
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
        url_path='product-consumption'
    )
    def product_consumption(self, request):
        """
        Get product consumption stats for the current calendar week (Mon–Sun).

        Query params:
        - statuses: Comma-separated order statuses (default: pending,confirmed,packing,completed)
        - category: Category ID to filter (optional)
        - limit: Max products to return (default: 20, max: 100)
        """
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())  # Monday
        week_end = week_start + timedelta(days=6)             # Sunday

        default_statuses = ['pending', 'confirmed', 'packing', 'completed']
        statuses_param = request.query_params.get('statuses', '')
        statuses = (
            [s.strip() for s in statuses_param.split(',') if s.strip()]
            if statuses_param
            else default_statuses
        )

        category_id = request.query_params.get('category')
        limit = min(int(request.query_params.get('limit', 20)), 100)

        qs = OrderItem.objects.filter(
            order__order_date__date__gte=week_start,
            order__order_date__date__lte=week_end,
            order__status__in=statuses,
        ).select_related('product__category')

        if category_id:
            qs = qs.filter(product__category_id=category_id)

        rows = (
            qs.values('product__id', 'product__name', 'product__category__name')
            .annotate(
                total_quantity=Sum('quantity'),
                order_count=Count('order', distinct=True),
            )
            .filter(total_quantity__gt=0)
            .order_by('-total_quantity')[:limit]
        )

        results = [
            {
                'product_id': r['product__id'],
                'product_name': r['product__name'],
                'category_name': r['product__category__name'],
                'total_quantity': r['total_quantity'],
                'order_count': r['order_count'],
                'avg_per_order': round(r['total_quantity'] / r['order_count']) if r['order_count'] else 0,
            }
            for r in rows
        ]

        return Response({
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat(),
            'statuses': statuses,
            'results': results,
        })

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated, IsStaffUser],
        url_path='product-consumption-trends'
    )
    def product_consumption_trends(self, request):
        """
        Get month-over-month consumption trends for the top N products.

        Query params:
        - months: Months to look back (default: 6, max: 12)
        - top: Number of top products (default: 5, max: 10)
        - category: Category ID to filter (optional)
        - statuses: Comma-separated statuses (default: pending,confirmed,packing,completed)
        """
        from calendar import month_abbr
        from django.db.models.functions import TruncMonth

        months_back = min(int(request.query_params.get('months', 6)), 12)
        top_n = min(int(request.query_params.get('top', 5)), 10)
        category_id = request.query_params.get('category')

        default_statuses = ['pending', 'confirmed', 'packing', 'completed']
        statuses_param = request.query_params.get('statuses', '')
        statuses = (
            [s.strip() for s in statuses_param.split(',') if s.strip()]
            if statuses_param
            else default_statuses
        )

        today = timezone.now()
        start_approx = today - timedelta(days=months_back * 30)
        start = today.replace(
            year=start_approx.year,
            month=start_approx.month,
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

        qs = OrderItem.objects.filter(
            order__order_date__gte=start,
            order__status__in=statuses,
        )
        if category_id:
            qs = qs.filter(product__category_id=category_id)

        # Top N products by total quantity in the period
        top_products = list(
            qs.values('product__id', 'product__name')
            .annotate(total=Sum('quantity'))
            .filter(total__gt=0)
            .order_by('-total')[:top_n]
        )

        if not top_products:
            return Response({
                'months': [], 'products': [], 'statuses': statuses,
                'period_start': start.date().isoformat(),
                'period_end': today.date().isoformat(),
            })

        top_ids = [r['product__id'] for r in top_products]
        top_names = {r['product__id']: r['product__name'] for r in top_products}

        # Monthly totals for top products
        monthly_rows = (
            qs.filter(product__id__in=top_ids)
            .annotate(month=TruncMonth('order__order_date'))
            .values('month', 'product__id')
            .annotate(total_quantity=Sum('quantity'))
            .order_by('month')
        )

        # Build YYYY-MM month keys from start to today
        months_list = []
        y, m = start.year, start.month
        while (y, m) <= (today.year, today.month):
            months_list.append(f'{y:04d}-{m:02d}')
            m += 1
            if m > 12:
                m = 1
                y += 1

        def month_label(ym: str) -> str:
            yr, mo = ym.split('-')
            return f'{month_abbr[int(mo)]} {yr}'

        from collections import defaultdict
        lookup: dict = defaultdict(lambda: defaultdict(int))
        for row in monthly_rows:
            mk = row['month'].strftime('%Y-%m')
            lookup[row['product__id']][mk] = row['total_quantity']

        products_data = [
            {
                'product_id': pid,
                'product_name': top_names[pid],
                'monthly_data': [
                    {
                        'month': mk,
                        'month_label': month_label(mk),
                        'total_quantity': lookup[pid].get(mk, 0),
                    }
                    for mk in months_list
                ],
            }
            for pid in top_ids
        ]

        return Response({
            'months': [month_label(mk) for mk in months_list],
            'products': products_data,
            'statuses': statuses,
            'period_start': start.date().isoformat(),
            'period_end': today.date().isoformat(),
        })

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated, IsStaffUser],
        url_path='product-consumption-mom'
    )
    def product_consumption_mom(self, request):
        """
        Month-over-month product consumption comparison.
        Returns top 20 products ordered by |change|, with current and previous
        month totals, absolute change, and % change.

        Query params:
        - category: Category ID to filter (optional)
        - statuses: Comma-separated statuses (default: pending,confirmed,packing,completed)
        - limit: Max products (default: 20, max: 50)
        """
        from calendar import month_abbr

        default_statuses = ['pending', 'confirmed', 'packing', 'completed']
        statuses_param = request.query_params.get('statuses', '')
        statuses = (
            [s.strip() for s in statuses_param.split(',') if s.strip()]
            if statuses_param
            else default_statuses
        )
        category_id = request.query_params.get('category')
        limit = min(int(request.query_params.get('limit', 20)), 50)

        today = timezone.now()

        # Current month: 1st of this month → today
        cur_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        cur_end = today

        # Previous month: 1st → last day of previous month
        prev_end = cur_start - timedelta(seconds=1)
        prev_start = prev_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        def month_label_dt(dt) -> str:
            return f'{month_abbr[dt.month]} {dt.year}'

        def totals_for_period(start, end):
            qs = OrderItem.objects.filter(
                order__order_date__gte=start,
                order__order_date__lte=end,
                order__status__in=statuses,
            )
            if category_id:
                qs = qs.filter(product__category_id=category_id)
            return {
                r['product__id']: r['total']
                for r in qs.values('product__id', 'product__name')
                .annotate(total=Sum('quantity'))
                .filter(total__gt=0)
            }

        def names_for_period(start, end):
            qs = OrderItem.objects.filter(
                order__order_date__gte=start,
                order__order_date__lte=end,
                order__status__in=statuses,
            )
            if category_id:
                qs = qs.filter(product__category_id=category_id)
            return {
                r['product__id']: (r['product__name'], r['product__category__name'])
                for r in qs.values('product__id', 'product__name', 'product__category__name')
                .distinct()
            }

        cur_totals = totals_for_period(cur_start, cur_end)
        prev_totals = totals_for_period(prev_start, prev_end)
        all_ids = set(cur_totals.keys()) | set(prev_totals.keys())

        # Get product names from whichever period has them
        cur_names = names_for_period(cur_start, cur_end)
        prev_names = names_for_period(prev_start, prev_end)
        all_names = {**prev_names, **cur_names}

        results = []
        for pid in all_ids:
            cur = cur_totals.get(pid, 0)
            prev = prev_totals.get(pid, 0)
            change = cur - prev
            pct_change = round((change / prev) * 100) if prev > 0 else None
            name, cat_name = all_names.get(pid, ('Unknown', 'Unknown'))
            results.append({
                'product_id': pid,
                'product_name': name,
                'category_name': cat_name,
                'current_qty': cur,
                'prev_qty': prev,
                'change': change,
                'pct_change': pct_change,
            })

        # Sort by absolute change descending, then current qty
        results.sort(key=lambda x: (-abs(x['change']), -x['current_qty']))
        results = results[:limit]

        return Response({
            'current_month': month_label_dt(today),
            'prev_month': month_label_dt(prev_start),
            'statuses': statuses,
            'results': results,
        })

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

    @action(detail=True, methods=['get'], url_path='download-primary-pdf')
    def download_primary_pdf(self, request, pk=None):
        """Download the primary order PDF for this combined order."""
        from apps.orders.utils.order_services import generate_combined_order_pdf
        combined_order = self.get_object()
        pdf_buffer = generate_combined_order_pdf(combined_order)
        pdf_buffer.seek(0)
        response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="primary_order_{combined_order.id}.pdf"'
        return response

    @action(detail=True, methods=['get'], url_path='download-packing-list-pdf')
    def download_packing_list_pdf(self, request, pk=None):
        """Download the first packing list PDF (or primary PDF if no packing lists)."""
        from apps.orders.utils.order_services import generate_combined_order_pdf, generate_packing_list_pdf
        combined_order = self.get_object()
        packing_lists = combined_order.packing_lists.all()
        if packing_lists.exists():
            packing_list = packing_lists.first()
            pdf_buffer = generate_packing_list_pdf(packing_list)
            pdf_buffer.seek(0)
            filename = f"packing_list_{combined_order.id}_{packing_list.packer.name.replace(' ', '_')}.pdf"
        else:
            pdf_buffer = generate_combined_order_pdf(combined_order)
            pdf_buffer.seek(0)
            filename = f"packing_list_{combined_order.id}.pdf"
        response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @action(detail=True, methods=['get'], url_path='download-all-packing-lists')
    def download_all_packing_lists(self, request, pk=None):
        """Download all packing lists and primary order as a ZIP."""
        from apps.orders.utils.order_services import generate_combined_order_pdf, generate_packing_list_pdf
        combined_order = self.get_object()
        packing_lists = combined_order.packing_lists.all()
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            primary_pdf = generate_combined_order_pdf(combined_order)
            primary_pdf.seek(0)
            zip_file.writestr(f"primary_order_{combined_order.id}.pdf", primary_pdf.read())
            for pl in packing_lists:
                pdf_buffer = generate_packing_list_pdf(pl)
                pdf_buffer.seek(0)
                filename = f"packing_list_{pl.packer.name.replace(' ', '_')}_{combined_order.id}.pdf"
                zip_file.writestr(filename, pdf_buffer.read())
        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="combined_order_{combined_order.id}_all_lists.zip"'
        return response

    @action(detail=True, methods=['post'])
    def uncombine(self, request, pk=None):
        """Uncombine orders and delete this combined order."""
        from apps.orders.tasks.helper.combined_order_helper import uncombine_order
        combined_order = self.get_object()
        count = uncombine_order(combined_order)
        combined_order.delete()
        return Response({
            'uncombined_count': count,
            'message': f'Released {count} orders from combined order.',
        })

    @action(detail=False, methods=['post'])
    def preview(self, request):
        """Preview eligible orders before creating a combined order."""
        from datetime import date
        from apps.lifeskills.models import Program
        from apps.orders.tasks.helper.combined_order_helper import (
            get_eligible_orders, get_split_preview, validate_split_strategy
        )
        program_id = request.data.get('program_id')
        start_date_str = request.data.get('start_date')
        end_date_str = request.data.get('end_date')
        split_strategy_override = request.data.get('split_strategy_override', '')
        if not all([program_id, start_date_str, end_date_str]):
            return Response(
                {'error': 'program_id, start_date, and end_date are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            program = Program.objects.get(id=program_id)
            start_date = date.fromisoformat(start_date_str)
            end_date = date.fromisoformat(end_date_str)
        except (Program.DoesNotExist, ValueError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        effective_strategy = split_strategy_override or program.default_split_strategy
        eligible_orders, excluded_orders, warnings = get_eligible_orders(program, start_date, end_date)
        errors = []
        if not eligible_orders:
            errors.append(
                f"No eligible orders found for {program.name} between {start_date} and {end_date}."
            )
        strategy_valid, strategy_errors = validate_split_strategy(program, effective_strategy)
        if not strategy_valid:
            errors.extend(strategy_errors)
        preview_data = {}
        if eligible_orders and strategy_valid:
            raw_preview = get_split_preview(eligible_orders, program, effective_strategy)
            split_preview = []
            for item in raw_preview.get('split_preview', []):
                packer = item.get('packer')
                split_preview.append({
                    'packer_id': packer.id if packer else None,
                    'packer_name': packer.name if packer else 'Unknown',
                    'order_count': item.get('order_count', 0),
                    'item_count': item.get('item_count', 0),
                    'categories': item.get('categories', []),
                })
            preview_data = {
                'order_count': raw_preview.get('order_count', 0),
                'total_items': raw_preview.get('total_items', 0),
                'total_value': str(raw_preview.get('total_value', '0')),
                'category_totals': raw_preview.get('category_totals', {}),
                'packer_count': raw_preview.get('packer_count', 0),
                'strategy': raw_preview.get('strategy', ''),
                'split_preview': split_preview,
            }
        strategy_choices = dict(CombinedOrder.SPLIT_STRATEGY_CHOICES)
        return Response({
            'program': {'id': program.id, 'name': program.name},
            'effective_strategy': effective_strategy,
            'strategy_display': strategy_choices.get(effective_strategy, effective_strategy),
            'eligible_orders': [{'id': o.id, 'order_number': o.order_number} for o in eligible_orders],
            'excluded_orders': [{'id': o.id, 'order_number': o.order_number} for o in excluded_orders],
            'eligible_count': len(eligible_orders),
            'excluded_count': len(excluded_orders),
            'warnings': warnings,
            'errors': errors,
            'preview_data': preview_data,
            'can_proceed': len(errors) == 0 and len(eligible_orders) > 0,
            'order_ids': [o.id for o in eligible_orders],
        })

    @action(detail=False, methods=['post'], url_path='create-with-packing')
    def create_with_packing(self, request):
        """Create a combined order with packing lists (used by the wizard UI)."""
        from apps.lifeskills.models import Program
        from apps.orders.tasks.helper.combined_order_helper import create_combined_order_with_packing
        program_id = request.data.get('program_id')
        order_ids = request.data.get('order_ids', [])
        strategy = request.data.get('strategy', 'none')
        name = request.data.get('name')
        if not program_id or not order_ids:
            return Response(
                {'error': 'program_id and order_ids are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            program = Program.objects.get(id=program_id)
            orders = list(Order.objects.filter(id__in=order_ids))
            if not orders:
                return Response(
                    {'error': 'No orders found with the provided IDs'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            combined_order, _packing_lists = create_combined_order_with_packing(
                program=program,
                orders=orders,
                strategy=strategy,
                name=name,
            )
            return Response(
                CombinedOrderSerializer(combined_order).data,
                status=status.HTTP_201_CREATED
            )
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except IntegrityError:
            return Response(
                {'error': (
                    f'A combined order already exists for {program.name} this week. '
                    'Delete or uncombine the existing one first.'
                )},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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

    @action(detail=True, methods=['get'], url_path='download-pdf')
    def download_pdf(self, request, pk=None):
        """Download this packing list as a PDF."""
        from apps.orders.utils.order_services import generate_packing_list_pdf
        packing_list = self.get_object()
        pdf_buffer = generate_packing_list_pdf(packing_list)
        pdf_buffer.seek(0)
        filename = f"packing_list_{packing_list.packer.name.replace(' ', '_')}_{packing_list.combined_order.id}.pdf"
        response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class FailedOrderAttemptViewSet(mixins.DestroyModelMixin, viewsets.ReadOnlyModelViewSet):
    """Read-only ViewSet for FailedOrderAttempt model (staff only, superuser delete)."""
    queryset = FailedOrderAttempt.objects.select_related(
        'participant', 'user'
    ).order_by('-created_at')
    serializer_class = FailedOrderAttemptSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter
    ]
    filterset_fields = ['participant', 'program_pause_active']
    search_fields = [
        'participant__name', 'user__username', 'error_summary', 'ip_address'
    ]
    ordering_fields = ['created_at', 'total_attempted']
    ordering = ['-created_at']

    def destroy(self, request, *args, **kwargs):
        """Only superusers may delete failed order attempts."""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Only superusers can delete failed order attempts.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)
