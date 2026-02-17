import json
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path
from django.utils.html import format_html
from .models import EmailLog, EmailType, OrderValidationLog, UserLoginLog, GraceAllowanceLog
import logging

logger = logging.getLogger(__name__)


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
            logger.exception("Error generating email preview for EmailType id=%s", pk)
            return JsonResponse({
                'success': False,
                'error': 'An internal error occurred while generating the preview.',
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


@admin.register(UserLoginLog)
class UserLoginLogAdmin(admin.ModelAdmin):
    """Admin for viewing user login/logout activity."""
    list_display = [
        'timestamp',
        'user_display',
        'action_display',
        'participant_display',
        'ip_address',
    ]
    list_filter = ['action', 'timestamp']
    search_fields = ['user__username', 'user__email', 'username_attempted', 'ip_address']
    readonly_fields = [
        'user',
        'username_attempted',
        'action',
        'ip_address',
        'user_agent',
        'timestamp',
        'participant',
    ]
    date_hierarchy = 'timestamp'
    
    def user_display(self, obj):
        """Display user or attempted username."""
        if obj.user:
            return f"{obj.user.username} ({obj.user.email})"
        return obj.username_attempted or "Unknown"
    user_display.short_description = "User"
    user_display.admin_order_field = 'user__username'
    
    def action_display(self, obj):
        """Colorize action status."""
        colors = {
            'login': 'green',
            'logout': 'gray',
            'failed_login': 'red',
        }
        color = colors.get(obj.action, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_action_display()
        )
    action_display.short_description = "Action"
    action_display.admin_order_field = 'action'
    
    def participant_display(self, obj):
        """Display participant if exists."""
        if obj.participant:
            return f"{obj.participant.name} ({obj.participant.customer_number})"
        return "-"
    participant_display.short_description = "Participant"
    participant_display.admin_order_field = 'participant__name'
    
    def has_add_permission(self, request):
        """Prevent manual creation."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion - audit trail."""
        return False


@admin.register(GraceAllowanceLog)
class GraceAllowanceLogAdmin(admin.ModelAdmin):
    """Admin interface for Grace Allowance Log entries."""
    
    list_display = [
        'participant_display',
        'order_link',
        'amount_over_display',
        'proceeded_display',
        'created_at'
    ]
    list_filter = ['proceeded', 'created_at']
    search_fields = [
        'participant__name',
        'participant__customer_number',
        'participant__user__username',
        'order__order_number'
    ]
    readonly_fields = [
        'participant',
        'order',
        'amount_over',
        'grace_message',
        'proceeded',
        'created_at'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Grace Allowance Details', {
            'fields': ('participant', 'order', 'amount_over', 'proceeded', 'created_at')
        }),
        ('Educational Message', {
            'fields': ('grace_message',),
            'description': 'Message shown to participant explaining the grace allowance.'
        }),
    )
    
    def participant_display(self, obj):
        """Display participant name and customer number."""
        return format_html(
            '<a href="/admin/account/participant/{}/change/">{}</a><br>'
            '<small style="color: #666;">Customer #{}</small>',
            obj.participant.id,
            obj.participant.name,
            obj.participant.customer_number
        )
    participant_display.short_description = 'Participant'
    participant_display.admin_order_field = 'participant__name'
    
    def order_link(self, obj):
        """Link to associated order."""
        if obj.order:
            return format_html(
                '<a href="/admin/orders/order/{}/change/">{}</a>',
                obj.order.id,
                obj.order.order_number
            )
        return format_html('<span style="color: gray;">No order</span>')
    order_link.short_description = 'Order'
    order_link.admin_order_field = 'order__order_number'
    
    def amount_over_display(self, obj):
        """Display amount over with color coding."""
        return format_html(
            '<span style="color: {}; font-weight: bold;">${:.2f}</span>',
            '#dc3545' if obj.amount_over > 0.50 else '#ffc107',
            obj.amount_over
        )
    amount_over_display.short_description = 'Amount Over'
    amount_over_display.admin_order_field = 'amount_over'
    
    def proceeded_display(self, obj):
        """Display whether participant proceeded with visual indicator."""
        if obj.proceeded:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Proceeded</span>'
            )
        return format_html(
            '<span style="color: gray;">✗ Reviewed Only</span>'
        )
    proceeded_display.short_description = 'Action Taken'
    proceeded_display.admin_order_field = 'proceeded'
    
    def has_add_permission(self, request):
        """Prevent manual creation - logs are auto-generated."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent editing - audit trail."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion - audit trail."""
        return False


admin.site.register(OrderValidationLog)
