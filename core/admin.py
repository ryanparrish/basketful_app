"""Admin configuration for core app."""
from django.contrib import admin
from django.utils.html import format_html
from .models import OrderWindowSettings, EmailSettings, BrandingSettings


@admin.register(OrderWindowSettings)
class OrderWindowSettingsAdmin(admin.ModelAdmin):
    """Admin interface for Order Window Settings."""
    
    list_display = [
        'hours_before_class',
        'hours_before_close',
        'enabled',
        'updated_at'
    ]
    
    fieldsets = (
        ('Order Window Configuration', {
            'fields': (
                'hours_before_class',
                'hours_before_close',
                'enabled'
            ),
            'description': (
                '<p><strong>Control when participants can place '
                'orders relative to their class schedule.</strong></p>'
                
                '<div style="margin-top: 15px;">'
                '<details style="margin-bottom: 10px;">'
                '<summary style="cursor: pointer; font-weight: bold; '
                'padding: 8px; background: #f8f9fa; border-radius: 4px;">'
                '📖 How It Works</summary>'
                '<div style="padding: 10px; border-left: 3px solid #007bff; '
                'margin-top: 5px;">'
                '<p>Participants can only place orders during a specific '
                'time window before their scheduled class. This window has '
                'both an opening time and a closing time.</p>'
                '</div>'
                '</details>'
                
                '<details open style="margin-bottom: 10px;">'
                '<summary style="cursor: pointer; font-weight: bold; '
                'padding: 8px; background: #f8f9fa; border-radius: 4px;">'
                '⚙️ Settings Explained</summary>'
                '<div style="padding: 10px; border-left: 3px solid #007bff; '
                'margin-top: 5px;">'
                '<ul style="line-height: 1.8; margin-top: 5px;">'
                
                '<li><strong>Hours Before Class (Window Opens):</strong><br>'
                'How many hours before class time the order window opens. '
                'This is when participants can <em>start</em> placing orders.'
                '<br><em>Example:</em> Set to 24 means orders can begin '
                '24 hours before class.</li>'
                
                '<li style="margin-top: 10px;"><strong>Hours Before Close:'
                '</strong><br>'
                'How many hours before class time the order window closes. '
                'This is the deadline - participants must complete their '
                'order before this time.'
                '<br><em>Example:</em> Set to 2 means orders must be placed '
                'at least 2 hours before class starts.'
                '<br><em>Set to 0</em> to allow orders right up until '
                'class time.</li>'
                
                '<li style="margin-top: 10px;"><strong>Enabled:</strong><br>'
                'Turn this OFF to disable time restrictions and allow '
                'participants to order anytime. Useful for testing or '
                'special circumstances.</li>'
                
                '</ul>'
                '</div>'
                '</details>'
                
                '<details style="margin-bottom: 10px;">'
                '<summary style="cursor: pointer; font-weight: bold; '
                'padding: 8px; background: #f8f9fa; border-radius: 4px;">'
                '💡 Complete Example</summary>'
                '<div style="padding: 10px; border-left: 3px solid #007bff; '
                'margin-top: 5px;">'
                '<div style="background: #fff; padding: 12px; '
                'border: 1px solid #dee2e6; border-radius: 4px;">'
                '<p style="margin: 0;"><strong>Class Schedule:</strong> '
                'Wednesday at 2:00 PM</p>'
                '<p style="margin: 5px 0 0 0;"><strong>Settings:</strong> '
                'Opens 24 hours before, Closes 2 hours before</p>'
                '<p style="margin: 5px 0 0 0; color: #28a745;">'
                '<strong>✓ Order Window:</strong> '
                'Tuesday 2:00 PM → Wednesday 12:00 PM</p>'
                '<p style="margin: 5px 0 0 0; color: #dc3545;">'
                '<strong>✗ Orders Blocked:</strong> '
                'Wednesday 12:00 PM → Wednesday 2:00 PM</p>'
                '</div>'
                '</div>'
                '</details>'
                
                '<details style="margin-bottom: 10px;">'
                '<summary style="cursor: pointer; font-weight: bold; '
                'padding: 8px; background: #f8f9fa; border-radius: 4px;">'
                '🔧 Common Configurations</summary>'
                '<div style="padding: 10px; border-left: 3px solid #007bff; '
                'margin-top: 5px;">'
                '<ul style="line-height: 1.6; margin-top: 5px;">'
                '<li><strong>24 hours open, 0 close:</strong> Full 24-hour '
                'window ending at class time</li>'
                '<li><strong>24 hours open, 2 close:</strong> 22-hour '
                'window with 2-hour preparation buffer</li>'
                '<li><strong>48 hours open, 4 close:</strong> 44-hour '
                'window with 4-hour preparation time</li>'
                '</ul>'
                '</div>'
                '</details>'
                '</div>'
            )
        }),
    )
    
    def has_add_permission(self, request):
        """Prevent adding multiple instances (singleton)."""
        return not OrderWindowSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of the settings."""
        return False


@admin.register(EmailSettings)
class EmailSettingsAdmin(admin.ModelAdmin):
    """Admin interface for Email Settings (singleton)."""
    
    list_display = ['from_email_default', 'reply_to_default', 'updated_at']
    
    fieldsets = (
        ('Default Email Addresses', {
            'fields': ('from_email_default', 'reply_to_default'),
            'description': (
                '<p><strong>Configure global default email addresses.</strong></p>'
                '<p>These defaults are used when individual Email Types do not '
                'specify their own from/reply-to addresses.</p>'
                '<ul>'
                '<li><strong>From Email:</strong> Leave blank to use Django\'s '
                'DEFAULT_FROM_EMAIL setting.</li>'
                '<li><strong>Reply-To:</strong> The default reply-to address '
                'for all outgoing emails.</li>'
                '</ul>'
            ),
        }),
    )
    
    def has_add_permission(self, request):
        """Prevent adding multiple instances (singleton)."""
        return not EmailSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of the settings."""
        return False


@admin.register(BrandingSettings)
class BrandingSettingsAdmin(admin.ModelAdmin):
    """Admin interface for Branding Settings."""
    
    list_display = ['organization_name', 'has_logo', 'updated_at']
    
    fieldsets = (
        ('Organization Branding', {
            'fields': ('organization_name', 'logo'),
            'description': (
                '<p><strong>Configure organization branding for printed orders.</strong></p>'
                '<p>Upload a logo and set your organization name. '
                'These will appear on all printed order documents.</p>'
            )
        }),
    )
    
    def has_logo(self, obj):
        """Display whether a logo is uploaded."""
        if obj.logo:
            return format_html(
                '<span style="color: green;">✓ Uploaded</span>'
            )
        return format_html(
            '<span style="color: gray;">✗ No logo</span>'
        )
    has_logo.short_description = 'Logo Status'
    
    def has_add_permission(self, request):
        """Only allow one instance (singleton)."""
        return not BrandingSettings.objects.exists()
    
    def get_queryset(self, request):
        """Limit queryset to single instance."""
        return BrandingSettings.objects.all()[:1]
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of singleton."""
        return False
