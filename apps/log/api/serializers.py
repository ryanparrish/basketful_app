"""
Serializers for the Log app.
"""
from rest_framework import serializers

from apps.log.models import (
    EmailType,
    EmailLog,
    VoucherLog,
    OrderValidationLog,
    UserLoginLog,
    GraceAllowanceLog,
)


class EmailTypeSerializer(serializers.ModelSerializer):
    """Serializer for EmailType model.

    Exposes the per-language modeltranslation columns explicitly so the
    email studio can edit English and Spanish side by side. The base
    columns stay writable for back-compat, but writing them writes the
    active-language column — prefer the explicit ``_en``/``_es`` fields.
    """
    variables = serializers.SerializerMethodField()

    class Meta:
        model = EmailType
        fields = [
            'id', 'name', 'display_name', 'subject',
            'subject_en', 'subject_es',
            'html_template', 'text_template',
            'html_content', 'html_content_en', 'html_content_es',
            'text_content', 'text_content_en', 'text_content_es',
            'from_email', 'reply_to',
            'available_variables', 'description', 'variables',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'variables', 'created_at', 'updated_at']

    def get_variables(self, obj) -> list:
        """Template variables available to this email type (see apps/log/variables.py)."""
        from apps.log.variables import get_variables
        return [
            {
                'token': variable.token,
                'label': variable.label,
                'description': variable.description,
                'sample_value': variable.sample_value,
                'kind': variable.kind,
                'item_attributes': list(variable.item_attributes),
            }
            for variable in get_variables(obj.name)
        ]


class EmailTypeListSerializer(serializers.ModelSerializer):
    """Simplified serializer for EmailType list views."""

    class Meta:
        model = EmailType
        fields = [
            'id', 'name', 'display_name', 'subject', 'is_active'
        ]
        read_only_fields = ['id']


class EmailLogSerializer(serializers.ModelSerializer):
    """Serializer for EmailLog model."""
    email_type_name = serializers.CharField(
        source='email_type.display_name', read_only=True
    )
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = EmailLog
        fields = [
            'id', 'user', 'user_email', 'email_type', 'email_type_name',
            'subject', 'status', 'error_message', 'sent_at', 'message_id',
            'delivery_status', 'delivery_checked_at',
        ]
        read_only_fields = ['id', 'sent_at', 'delivery_checked_at']


class VoucherLogSerializer(serializers.ModelSerializer):
    """Serializer for VoucherLog model."""
    participant_name = serializers.CharField(
        source='participant.name', read_only=True
    )

    class Meta:
        model = VoucherLog
        fields = [
            'id', 'participant', 'participant_name', 'user', 'order',
            'voucher', 'message', 'log_type',
            'balance_before', 'balance_after', 'applied_amount', 'remaining',
            'validated_at', 'created_at'
        ]
        read_only_fields = ['id', 'validated_at', 'created_at']


class OrderValidationLogSerializer(serializers.ModelSerializer):
    """Serializer for OrderValidationLog model."""
    participant_name = serializers.CharField(
        source='participant.name', read_only=True
    )
    product_name = serializers.CharField(
        source='product.name', read_only=True
    )

    class Meta:
        model = OrderValidationLog
        fields = [
            'id', 'participant', 'participant_name', 'user', 'order',
            'product', 'product_name', 'message', 'log_type',
            'validated_at', 'created_at'
        ]
        read_only_fields = ['id', 'validated_at', 'created_at']


class UserLoginLogSerializer(serializers.ModelSerializer):
    """Serializer for UserLoginLog model."""
    username = serializers.CharField(source='user.username', read_only=True)
    participant_name = serializers.CharField(
        source='participant.name', read_only=True
    )

    class Meta:
        model = UserLoginLog
        fields = [
            'id', 'user', 'username', 'username_attempted', 'action',
            'ip_address', 'user_agent', 'timestamp',
            'participant', 'participant_name'
        ]
        read_only_fields = ['id', 'timestamp']


class GraceAllowanceLogSerializer(serializers.ModelSerializer):
    """Serializer for GraceAllowanceLog model."""
    participant_name = serializers.CharField(
        source='participant.name', read_only=True
    )
    participant_customer_number = serializers.CharField(
        source='participant.customer_number', read_only=True
    )
    order_number = serializers.CharField(
        source='order.order_number', read_only=True
    )

    class Meta:
        model = GraceAllowanceLog
        fields = [
            'id', 'participant', 'participant_name', 'participant_customer_number',
            'order', 'order_number',
            'amount_over', 'grace_message', 'proceeded', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
