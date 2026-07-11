"""
Serializers for the Core app.
"""
from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta

from core.models import (
    OrderWindowSettings,
    EmailSettings,
    BrandingSettings,
    ProgramSettings,
    ThemeSettings,
    ProgramOrderWindow,
    ProgramWindowOverride,
)


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
        except Exception:
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
        except Exception:
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
        except Exception:
            return None


class EmailSettingsSerializer(serializers.ModelSerializer):
    """Serializer for EmailSettings model."""
    effective_from_email = serializers.SerializerMethodField()
    effective_participant_frontend_url = serializers.SerializerMethodField()
    effective_backend_domain = serializers.SerializerMethodField()

    class Meta:
        model = EmailSettings
        fields = [
            'id', 'from_email_default', 'reply_to_default',
            'participant_frontend_url', 'backend_domain',
            'effective_from_email', 'effective_participant_frontend_url',
            'effective_backend_domain', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_effective_from_email(self, obj) -> str:
        return obj.get_from_email()

    def get_effective_participant_frontend_url(self, obj) -> str:
        return obj.get_participant_frontend_url()

    def get_effective_backend_domain(self, obj) -> str:
        return obj.get_backend_domain()


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
    recaptcha_site_key = serializers.SerializerMethodField()

    class Meta:
        model = ProgramSettings
        fields = [
            'id', 'grace_amount', 'grace_enabled', 'grace_message',
            'grace_message_en', 'grace_message_es',
            'rules_version', 'recaptcha_site_key', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'rules_version', 'recaptcha_site_key', 'created_at', 'updated_at']
        extra_kwargs = {
            'grace_message_en': {'required': False, 'allow_null': True, 'allow_blank': True},
            'grace_message_es': {'required': False, 'allow_null': True, 'allow_blank': True},
        }

    def get_recaptcha_site_key(self, obj):
        """Get reCAPTCHA site key from Django settings."""
        from django.conf import settings
        return getattr(settings, 'RECAPTCHA_PUBLIC_KEY', None)


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


# ---------------------------------------------------------------------------
# Per-program order window serializers
# ---------------------------------------------------------------------------


class ProgramOrderWindowSerializer(serializers.ModelSerializer):
    """
    Sparse per-program order window config override.

    Null fields mean "inherit from the global OrderWindowSettings singleton".
    The frontend uses the *_source fields to render '(global)' labels.
    """
    # Read-only effective / source fields — derived, never stored
    effective_hours_before_class = serializers.SerializerMethodField()
    effective_hours_before_close = serializers.SerializerMethodField()
    effective_enabled = serializers.SerializerMethodField()
    hours_before_class_source = serializers.SerializerMethodField()
    hours_before_close_source = serializers.SerializerMethodField()
    enabled_source = serializers.SerializerMethodField()

    class Meta:
        model = ProgramOrderWindow
        fields = [
            'hours_before_class',
            'hours_before_close',
            'enabled',
            'effective_hours_before_class',
            'effective_hours_before_close',
            'effective_enabled',
            'hours_before_class_source',
            'hours_before_close_source',
            'enabled_source',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'effective_hours_before_class',
            'effective_hours_before_close',
            'effective_enabled',
            'hours_before_class_source',
            'hours_before_close_source',
            'enabled_source',
            'created_at',
            'updated_at',
        ]

    def _get_config(self, obj):
        from core.utils import get_effective_config
        return get_effective_config(obj.program)

    def get_effective_hours_before_class(self, obj):
        return self._get_config(obj)['hours_before_class']

    def get_effective_hours_before_close(self, obj):
        return self._get_config(obj)['hours_before_close']

    def get_effective_enabled(self, obj):
        return self._get_config(obj)['enabled']

    def get_hours_before_class_source(self, obj):
        return self._get_config(obj)['hours_before_class_source']

    def get_hours_before_close_source(self, obj):
        return self._get_config(obj)['hours_before_close_source']

    def get_enabled_source(self, obj):
        return self._get_config(obj)['enabled_source']


class ProgramWindowOverrideSerializer(serializers.ModelSerializer):
    """Active manual force-open / force-close for a program."""
    created_by_username = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = ProgramWindowOverride
        fields = [
            'id',
            'force_status',
            'expires_at',
            'reason',
            'created_by_username',
            'is_active',
            'created_at',
        ]
        read_only_fields = ['id', 'created_by_username', 'is_active', 'created_at']

    def get_created_by_username(self, obj):
        return obj.created_by.username if obj.created_by else None

    def get_is_active(self, obj):
        return obj.is_active()


class WindowCycleSerializer(serializers.Serializer):
    """One open→class window cycle (computed, not stored)."""
    meeting_at = serializers.DateTimeField()
    opens_at = serializers.DateTimeField()
    closes_at = serializers.DateTimeField()


class EffectiveConfigSerializer(serializers.Serializer):
    """Resolved order-window config for a program (COALESCE output)."""
    hours_before_class = serializers.IntegerField()
    hours_before_close = serializers.IntegerField()
    enabled = serializers.BooleanField()
    is_overridden = serializers.BooleanField()
    hours_before_class_source = serializers.CharField()
    hours_before_close_source = serializers.CharField()
    enabled_source = serializers.CharField()


class ProgramWindowStatusSerializer(serializers.Serializer):
    """
    Full computed status snapshot for one program.

    Returned by the dashboard polling endpoint and by the per-program
    order-window detail view.  Nothing here is stored — it is derived
    entirely from Program, ProgramOrderWindow, ProgramWindowOverride,
    and OrderWindowSettings at request time.
    """
    program_id = serializers.IntegerField()
    program_name = serializers.CharField()
    meeting_day = serializers.CharField()
    meeting_time = serializers.CharField()
    window_status = serializers.ChoiceField(choices=[
        'open', 'closed', 'force_open', 'force_closed', 'disabled', 'no_schedule',
    ])
    cycles = WindowCycleSerializer(many=True)
    seconds_until_change = serializers.IntegerField(allow_null=True)
    active_order_count = serializers.IntegerField()
    override = ProgramWindowOverrideSerializer(allow_null=True)
    config = EffectiveConfigSerializer()