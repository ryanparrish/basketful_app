"""Admin configuration for core app."""
from django.contrib import admin
from django.utils.html import format_html
from .models import OrderWindowSettings, EmailSettings, BrandingSettings, ProgramSettings, ThemeSettings


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


@admin.register(ProgramSettings)
class ProgramSettingsAdmin(admin.ModelAdmin):
    """Admin interface for Program Settings including grace allowance."""
    
    list_display = ['grace_amount', 'grace_enabled', 'rules_version_display', 'updated_at']
    
    fieldsets = (
        ('Grace Allowance Configuration', {
            'fields': ('grace_enabled', 'grace_amount', 'grace_message'),
            'description': (
                '<p><strong>Configure grace allowance for financial literacy learning.</strong></p>'
                '<p>Grace allowance allows participants to exceed their budget by a small amount '
                'as a learning opportunity. This helps teach financial accountability.</p>'
                '<ul>'
                '<li><strong>Grace Enabled:</strong> Turn on/off the grace allowance feature</li>'
                '<li><strong>Grace Amount:</strong> Maximum dollar amount over budget allowed (default $1.00)</li>'
                '<li><strong>Grace Message:</strong> Educational message shown to participants when using grace allowance</li>'
                '</ul>'
            )
        }),
        ('System Information', {
            'fields': ('rules_version',),
            'description': (
                '<p><strong>Rules Version:</strong> Auto-generated hash tracking business rule changes. '
                'This helps the frontend know when to refresh validation data.</p>'
            )
        }),
    )
    
    readonly_fields = ['rules_version']
    
    def rules_version_display(self, obj):
        """Display shortened version of rules hash."""
        if obj.rules_version:
            return format_html(
                '<code style="background: #f8f9fa; padding: 2px 6px; border-radius: 3px;">{}</code>',
                obj.rules_version[:12] + '...'
            )
        return format_html('<span style="color: gray;">Not generated</span>')
    rules_version_display.short_description = 'Rules Version'
    
    def has_add_permission(self, request):
        """Only allow one instance (singleton)."""
        return not ProgramSettings.objects.exists()
    
    def get_queryset(self, request):
        """Limit queryset to single instance."""
        return ProgramSettings.objects.all()[:1]
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of singleton."""
        return False


@admin.register(ThemeSettings)
class ThemeSettingsAdmin(admin.ModelAdmin):
    """Admin interface for Theme Settings for participant frontend."""
    
    list_display = ['app_name', 'primary_color_preview', 'secondary_color_preview', 'has_logo', 'updated_at']
    
    fieldsets = (
        ('Application Branding', {
            'fields': ('app_name', 'logo', 'favicon'),
            'description': (
                '<p><strong>Configure branding for the participant frontend application.</strong></p>'
                '<p>Set the application name and upload logo/favicon images.</p>'
            )
        }),
        ('Color Theme', {
            'fields': ('primary_color', 'secondary_color'),
            'description': (
                '<p><strong>Customize the color scheme of the participant frontend.</strong></p>'
                '<p>Use hex color codes (e.g., #1976d2). Changes will be reflected in the mobile app '
                'after the frontend refetches theme settings (every 4 hours or on manual refresh).</p>'
                '<p><em>Note:</em> Theme updates are cached for 4 hours. Users may need to wait or '
                'refresh their browser to see changes immediately.</p>'
            )
        }),
    )
    
    def primary_color_preview(self, obj):
        """Show color preview for primary color."""
        return format_html(
            '<div style="display: inline-block; width: 60px; height: 20px; '
            'background-color: {}; border: 1px solid #ccc; border-radius: 3px; '
            'vertical-align: middle;"></div> <code>{}</code>',
            obj.primary_color, obj.primary_color
        )
    primary_color_preview.short_description = 'Primary Color'
    
    def secondary_color_preview(self, obj):
        """Show color preview for secondary color."""
        return format_html(
            '<div style="display: inline-block; width: 60px; height: 20px; '
            'background-color: {}; border: 1px solid #ccc; border-radius: 3px; '
            'vertical-align: middle;"></div> <code>{}</code>',
            obj.secondary_color, obj.secondary_color
        )
    secondary_color_preview.short_description = 'Secondary Color'
    
    def has_logo(self, obj):
        """Display whether a logo is uploaded."""
        if obj.logo:
            return format_html('<span style="color: green;">✓ Uploaded</span>')
        return format_html('<span style="color: gray;">✗ No logo</span>')
    has_logo.short_description = 'Logo Status'
    
    def has_add_permission(self, request):
        """Only allow one instance (singleton)."""
        return not ThemeSettings.objects.exists()
    
    def get_queryset(self, request):
        """Limit queryset to single instance."""
        return ThemeSettings.objects.all()[:1]
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of singleton."""
        return False
