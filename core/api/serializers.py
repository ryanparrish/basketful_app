"""
Serializers for the Core app.
"""
from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta

from core.models import OrderWindowSettings, EmailSettings, BrandingSettings, ProgramSettings, ThemeSettings


class OrderWindowSettingsSerializer(serializers.ModelSerializer):
    """Serializer for OrderWindowSettings model with computed is_open field."""
    is_open = serializers.SerializerMethodField()
    next_opens_at = serializers.SerializerMethodField()
    next_closes_at = serializers.SerializerMethodField()

    class Meta:
        model = OrderWindowSettings
        fields = [
            'id', 'hours_before_class', 'hours_before_close',
            'enabled', 'is_open', 'next_opens_at', 'next_closes_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_open', 'next_opens_at', 'next_closes_at']
    
    def get_is_open(self, obj):
        """Calculate if order window is currently open."""
        if not obj.enabled:
            return False
        
        try:
            from apps.lifeskills.models import Lifeskills
            # Get next upcoming class
            now = timezone.now()
            next_class = Lifeskills.objects.filter(
                date__gte=now
            ).order_by('date').first()
            
            if not next_class:
                return False
            
            # Calculate window open/close times
            window_opens = next_class.date - timedelta(hours=obj.hours_before_class)
            window_closes = next_class.date - timedelta(hours=obj.hours_before_close)
            
            return window_opens <= now <= window_closes
        except:
            # If can't determine, default to closed for safety
            return False
    
    def get_next_opens_at(self, obj):
        """Get timestamp when order window next opens."""
        if not obj.enabled:
            return None
        
        try:
            from apps.lifeskills.models import Lifeskills
            now = timezone.now()
            next_class = Lifeskills.objects.filter(
                date__gte=now
            ).order_by('date').first()
            
            if not next_class:
                return None
            
            window_opens = next_class.date - timedelta(hours=obj.hours_before_class)
            return window_opens.isoformat() if window_opens > now else None
        except:
            return None
    
    def get_next_closes_at(self, obj):
        """Get timestamp when order window next closes."""
        if not obj.enabled:
            return None
        
        try:
            from apps.lifeskills.models import Lifeskills
            now = timezone.now()
            next_class = Lifeskills.objects.filter(
                date__gte=now
            ).order_by('date').first()
            
            if not next_class:
                return None
            
            window_closes = next_class.date - timedelta(hours=obj.hours_before_close)
            return window_closes.isoformat() if window_closes > now else None
        except:
            return None


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


class ProgramSettingsSerializer(serializers.ModelSerializer):
    """Serializer for ProgramSettings model."""

    class Meta:
        model = ProgramSettings
        fields = [
            'id', 'grace_amount', 'grace_enabled', 'grace_message',
            'rules_version', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'rules_version', 'created_at', 'updated_at']


class ThemeSettingsSerializer(serializers.ModelSerializer):
    """Serializer for ThemeSettings model with absolute URLs for images."""
    logo_url = serializers.SerializerMethodField()
    favicon_url = serializers.SerializerMethodField()

    class Meta:
        model = ThemeSettings
        fields = [
            'id', 'primary_color', 'secondary_color', 'app_name',
            'logo', 'logo_url', 'favicon', 'favicon_url',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'logo_url', 'favicon_url']
    
    def get_logo_url(self, obj):
        """Get absolute URL for logo image."""
        if obj.logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return None
    
    def get_favicon_url(self, obj):
        """Get absolute URL for favicon image."""
        if obj.favicon:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.favicon.url)
            return obj.favicon.url
        return None
