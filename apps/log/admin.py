import json
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path
from django.utils.html import format_html
from .models import EmailLog, EmailType, OrderValidationLog


@admin.register(EmailType)
class EmailTypeAdmin(admin.ModelAdmin):
    """Admin for EmailType with TinyMCE editor and preview functionality."""
    
    list_display = (
        'display_name',
        'name',
        'is_active',
        'has_html_content',
        'has_text_content',
        'updated_at'
    )
    list_filter = ('is_active',)
    search_fields = ('name', 'display_name', 'subject')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'subject', 'is_active'),
        }),
        ('Email Content (Editable)', {
            'fields': ('html_content', 'text_content'),
            'description': (
                'Edit email content directly here. These fields take priority '
                'over template files. Use Django template syntax for variables.'
            ),
        }),
        ('Fallback Template Files', {
            'fields': ('html_template', 'text_template'),
            'classes': ('collapse',),
            'description': (
                'Template file paths used as fallback when content fields are empty. '
                'Can be left blank for future email types.'
            ),
        }),
        ('Email Addresses', {
            'fields': ('from_email', 'reply_to'),
            'description': 'Leave blank to use global defaults from Email Settings.',
        }),
        ('Documentation', {
            'fields': ('available_variables', 'description'),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    change_form_template = 'admin/log/emailtype/change_form.html'
    
    def has_html_content(self, obj):
        """Display indicator for HTML content."""
        if obj.html_content:
            return format_html('<span style="color: green;">✓ Database</span>')
        elif obj.html_template:
            return format_html('<span style="color: blue;">📄 File</span>')
        return format_html('<span style="color: gray;">—</span>')
    has_html_content.short_description = "HTML"
    
    def has_text_content(self, obj):
        """Display indicator for text content."""
        if obj.text_content:
            return format_html('<span style="color: green;">✓ Database</span>')
        elif obj.text_template:
            return format_html('<span style="color: blue;">📄 File</span>')
        return format_html('<span style="color: gray;">—</span>')
    has_text_content.short_description = "Text"
    
    def get_urls(self):
        """Add custom URL for email preview."""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:pk>/preview/',
                self.admin_site.admin_view(self.preview_view),
                name='log_emailtype_preview',
            ),
        ]
        return custom_urls + urls
    
    def preview_view(self, request, pk):
        """Return rendered email preview as JSON."""
        try:
            email_type = EmailType.objects.get(pk=pk)
            context = EmailType.get_sample_context()
            
            html_content = email_type.render_html(context)
            text_content = email_type.render_text(context)
            subject = email_type.render_subject(context)
            
            return JsonResponse({
                'success': True,
                'subject': subject,
                'html': html_content,
                'text': text_content,
                'display_name': email_type.display_name,
            })
        except EmailType.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Email type not found',
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
            }, status=500)


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    """Admin for EmailLog with read-only fields and search."""
    list_display = ('id', 'user', 'email_type', 'subject', 'status', 'sent_at')
    list_filter = ('status', 'email_type', 'sent_at')
    search_fields = ('user__email', 'user__username', 'subject')
    readonly_fields = (
        'user', 'email_type', 'subject', 'status',
        'error_message', 'sent_at', 'message_id'
    )
    ordering = ('-sent_at',)
    
    def has_add_permission(self, request):
        """Prevent manual creation of email logs."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of email logs."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent editing of email logs."""
        return False


admin.site.register(OrderValidationLog)
