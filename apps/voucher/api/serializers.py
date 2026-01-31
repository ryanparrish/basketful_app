"""
Serializers for the Voucher app.
"""
from decimal import Decimal
from rest_framework import serializers

from apps.voucher.models import Voucher, VoucherSetting, OrderVoucher


class VoucherSettingSerializer(serializers.ModelSerializer):
    """Serializer for VoucherSetting model."""

    class Meta:
        model = VoucherSetting
        fields = [
            'id', 'adult_amount', 'child_amount', 'infant_modifier',
            'active', 'updated_at'
        ]
        read_only_fields = ['id', 'updated_at']


class VoucherSerializer(serializers.ModelSerializer):
    """Serializer for Voucher model."""
    voucher_amnt = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    participant_name = serializers.CharField(
        source='account.participant.name', read_only=True
    )
    participant_customer_number = serializers.CharField(
        source='account.participant.customer_number', read_only=True
    )
    program_name = serializers.CharField(
        source='account.participant.program.name', read_only=True
    )

    class Meta:
        model = Voucher
        fields = [
            'id', 'account', 'participant_name', 'participant_customer_number',
            'program_name', 'active', 'voucher_type', 'state',
            'program_pause_flag', 'multiplier', 'voucher_amnt', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'state', 'multiplier', 'voucher_amnt',
            'created_at', 'updated_at'
        ]


class VoucherListSerializer(serializers.ModelSerializer):
    """Simplified serializer for Voucher list views."""
    voucher_amnt = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    participant_name = serializers.CharField(
        source='account.participant.name', read_only=True
    )

    class Meta:
        model = Voucher
        fields = [
            'id', 'participant_name', 'active', 'voucher_type',
            'state', 'voucher_amnt', 'created_at'
        ]
        read_only_fields = ['id', 'state', 'voucher_amnt', 'created_at']


class VoucherCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Vouchers."""

    class Meta:
        model = Voucher
        fields = ['account', 'voucher_type', 'notes', 'program_pause_flag']


class BulkVoucherCreateSerializer(serializers.Serializer):
    """Serializer for bulk voucher creation."""
    account_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of account IDs to create vouchers for"
    )
    program_id = serializers.IntegerField(
        required=False,
        help_text="Create vouchers for all active participants in this program"
    )
    voucher_type = serializers.ChoiceField(
        choices=Voucher.VOUCHER_TYPE_CHOICES,
        default='grocery'
    )
    notes = serializers.CharField(required=False, default='', allow_blank=True)

    def validate(self, data):
        if not data.get('account_ids') and not data.get('program_id'):
            raise serializers.ValidationError(
                "Either 'account_ids' or 'program_id' must be provided."
            )
        return data


class OrderVoucherSerializer(serializers.ModelSerializer):
    """Serializer for OrderVoucher model."""
    order_number = serializers.CharField(
        source='order.order_number', read_only=True
    )
    voucher_type = serializers.CharField(
        source='voucher.voucher_type', read_only=True
    )

    class Meta:
        model = OrderVoucher
        fields = [
            'id', 'order', 'order_number', 'voucher', 'voucher_type',
            'applied_amount', 'applied_at'
        ]
        read_only_fields = ['id', 'applied_at']
