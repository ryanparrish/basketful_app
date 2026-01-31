"""
Serializers for the Core app.
"""
from rest_framework import serializers

from core.models import OrderWindowSettings, EmailSettings, BrandingSettings


class OrderWindowSettingsSerializer(serializers.ModelSerializer):
    """Serializer for OrderWindowSettings model."""

    class Meta:
        model = OrderWindowSettings
        fields = [
            'id', 'hours_before_class', 'hours_before_close',
            'enabled', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmailSettingsSerializer(serializers.ModelSerializer):
    """Serializer for EmailSettings model."""
    effective_from_email = serializers.SerializerMethodField()

    class Meta:
        model = EmailSettings
        fields = [
            'id', 'from_email_default', 'reply_to_default',
            'effective_from_email', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_effective_from_email(self, obj) -> str:
        return obj.get_from_email()


class BrandingSettingsSerializer(serializers.ModelSerializer):
    """Serializer for BrandingSettings model."""

    class Meta:
        model = BrandingSettings
        fields = [
            'id', 'organization_name', 'logo', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
