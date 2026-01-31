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
)


class EmailTypeSerializer(serializers.ModelSerializer):
    """Serializer for EmailType model."""

    class Meta:
        model = EmailType
        fields = [
            'id', 'name', 'display_name', 'subject',
            'html_template', 'text_template',
            'html_content', 'text_content',
            'from_email', 'reply_to',
            'available_variables', 'description',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


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
            'subject', 'status', 'error_message', 'sent_at', 'message_id'
        ]
        read_only_fields = ['id', 'sent_at']


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
