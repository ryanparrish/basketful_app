"""
Serializers for the Orders app.
"""
from decimal import Decimal
from rest_framework import serializers

from apps.orders.models import (
    Order,
    OrderItem,
    FailedOrderAttempt,
    CombinedOrder,
    PackingSplitRule,
    PackingList,
)
from apps.log.models import OrderValidationLog
from apps.pantry.api.serializers import ProductListSerializer


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for OrderItem model."""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_category = serializers.CharField(
        source='product.category.name', read_only=True
    )
    total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            'id', 'order', 'product', 'product_name', 'product_category',
            'quantity', 'price', 'price_at_order', 'total', 'created_at'
        ]
        read_only_fields = ['id', 'price', 'price_at_order', 'created_at']

    def get_total(self, obj) -> Decimal:
        return obj.total_price()


class OrderItemCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating OrderItems."""

    class Meta:
        model = OrderItem
        fields = ['product', 'quantity']


class OrderValidationLogSerializer(serializers.ModelSerializer):
    """Serializer for OrderValidationLog model."""

    class Meta:
        model = OrderValidationLog
        fields = ['id', 'order', 'message', 'created_at']
        read_only_fields = ['id', 'created_at']


class FailedOrderAttemptSerializer(serializers.ModelSerializer):
    """Serializer for FailedOrderAttempt model."""
    participant_name = serializers.CharField(
        source='participant.name', read_only=True
    )
    validation_errors_display = serializers.SerializerMethodField()

    class Meta:
        model = FailedOrderAttempt
        fields = [
            'id', 'participant', 'participant_name', 'user', 
            'idempotency_key', 'cart_hash', 'total_attempted',
            'food_total', 'hygiene_total', 'full_balance', 
            'available_balance', 'hygiene_balance', 
            'program_pause_active', 'program_pause_name',
            'voucher_multiplier', 'active_voucher_count',
            'validation_errors', 'validation_errors_display',
            'error_summary', 'ip_address', 'user_agent', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def get_validation_errors_display(self, obj):
        """Format validation errors as readable text."""
        if not obj.validation_errors:
            return None
        errors = obj.validation_errors
        if isinstance(errors, list):
            return '\n'.join(f"• {err}" for err in errors)
        return str(errors)


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for Order model."""
    items = OrderItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()
    participant_name = serializers.CharField(
        source='account.participant.name', read_only=True
    )
    participant_customer_number = serializers.CharField(
        source='account.participant.customer_number', read_only=True
    )
    program_name = serializers.CharField(
        source='account.participant.program.name', read_only=True
    )
    is_combined = serializers.BooleanField(read_only=True)
    validation_logs = OrderValidationLogSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'user', 'account',
            'participant_name', 'participant_customer_number', 'program_name',
            'order_date', 'status', 'paid', 'go_fresh_total',
            'items', 'total_price', 'is_combined', 'validation_logs',
            'success_viewed', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'order_number', 'order_date', 'go_fresh_total',
            'created_at', 'updated_at'
        ]

    def get_total_price(self, obj) -> Decimal:
        return obj.total_price()


class OrderListSerializer(serializers.ModelSerializer):
    """Simplified serializer for Order list views."""
    total_price = serializers.SerializerMethodField()
    participant_name = serializers.CharField(
        source='account.participant.name', read_only=True
    )
    participant_customer_number = serializers.CharField(
        source='account.participant.customer_number', read_only=True
    )
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'participant_name',
            'participant_customer_number', 'status', 'paid',
            'total_price', 'item_count', 'order_date', 'created_at'
        ]
        read_only_fields = ['id', 'order_number', 'order_date', 'created_at']

    def get_total_price(self, obj) -> Decimal:
        return obj.total_price()

    def get_item_count(self, obj) -> int:
        return obj.items.count()


class OrderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Orders with comprehensive validation."""
    items = OrderItemCreateSerializer(many=True, required=False)

    class Meta:
        model = Order
        fields = ['account', 'items']

    def create(self, validated_data):
        """
        Create order using OrderOrchestration with idempotency and validation.
        """
        from apps.orders.utils.order_utils import OrderOrchestration
        from apps.orders.utils.order_validation import OrderItemData
        
        items_data = validated_data.pop('items', [])
        account = validated_data.get('account')
        
        # Convert to OrderItemData objects
        order_items = [
            OrderItemData(
                product=item_data['product'],
                quantity=item_data['quantity']
            )
            for item_data in items_data
        ]
        
        # Get request context for audit
        request = self.context.get('request')
        user = request.user if request else None
        request_meta = self.context.get('request_meta', {})
        
        # Use OrderOrchestration.create_order (handles all validation & logging)
        orchestrator = OrderOrchestration()
        order = orchestrator.create_order(
            account=account,
            order_items_data=order_items,
            user=user,
            request_meta=request_meta
        )
        
        return order


class CombinedOrderSerializer(serializers.ModelSerializer):
    """Serializer for CombinedOrder model."""
    program_name = serializers.CharField(source='program.name', read_only=True)
    order_count = serializers.SerializerMethodField()
    orders = OrderListSerializer(many=True, read_only=True)
    packing_lists = serializers.SerializerMethodField()

    class Meta:
        model = CombinedOrder
        fields = [
            'id', 'name', 'program', 'program_name', 'orders', 'order_count',
            'split_strategy', 'summarized_data', 'packing_lists',
            'is_parent', 'week', 'year', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'week', 'year', 'summarized_data', 'created_at', 'updated_at'
        ]

    def get_order_count(self, obj) -> int:
        return obj.orders.count()

    def get_packing_lists(self, obj):
        return PackingListSerializer(
            obj.packing_lists.all(), many=True
        ).data


class CombinedOrderListSerializer(serializers.ModelSerializer):
    """Simplified serializer for CombinedOrder list views."""
    program_name = serializers.CharField(source='program.name', read_only=True)
    order_count = serializers.SerializerMethodField()

    class Meta:
        model = CombinedOrder
        fields = [
            'id', 'name', 'program', 'program_name', 'order_count',
            'split_strategy', 'week', 'year', 'created_at'
        ]
        read_only_fields = ['id', 'week', 'year', 'created_at']

    def get_order_count(self, obj) -> int:
        return obj.orders.count()


class PackingSplitRuleSerializer(serializers.ModelSerializer):
    """Serializer for PackingSplitRule model."""
    program_name = serializers.CharField(source='program.name', read_only=True)
    packer_name = serializers.CharField(source='packer.name', read_only=True)
    category_names = serializers.SerializerMethodField()
    subcategory_names = serializers.SerializerMethodField()

    class Meta:
        model = PackingSplitRule
        fields = [
            'id', 'program', 'program_name', 'packer', 'packer_name',
            'categories', 'category_names', 'subcategories', 'subcategory_names',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_category_names(self, obj) -> list:
        return list(obj.categories.values_list('name', flat=True))

    def get_subcategory_names(self, obj) -> list:
        return list(obj.subcategories.values_list('name', flat=True))


class PackingListSerializer(serializers.ModelSerializer):
    """Serializer for PackingList model."""
    packer_name = serializers.CharField(source='packer.name', read_only=True)
    order_count = serializers.SerializerMethodField()
    category_names = serializers.SerializerMethodField()

    class Meta:
        model = PackingList
        fields = [
            'id', 'combined_order', 'packer', 'packer_name',
            'orders', 'order_count', 'categories', 'category_names',
            'summarized_data', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'summarized_data', 'created_at', 'updated_at'
        ]

    def get_order_count(self, obj) -> int:
        return obj.orders.count()

    def get_category_names(self, obj) -> list:
        return list(obj.categories.values_list('name', flat=True))
