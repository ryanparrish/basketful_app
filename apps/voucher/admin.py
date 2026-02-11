# apps/voucher/admin.py
"""Admin configuration for Voucher and VoucherSetting models."""
# Django imports
from django.contrib import admin, messages
from django.urls import path
# First Party imports
from apps.log.inlines import VoucherLogInline
# Local imports
from .models import Voucher, VoucherSetting
from . import views as voucher_views
from . import views_reports


@admin.action(description="Mark selected vouchers as Applied")
def mark_as_applied(modeladmin, request, queryset):
    """Mark selected vouchers as Applied."""
    updated = queryset.update(state='applied')
    if updated:
        messages.success(request, f"{updated} voucher(s) marked as Applied.")
    else:
        messages.warning(request, "No vouchers were updated.")


@admin.register(Voucher)
class VoucherAdmin(admin.Mwe codelAdmin):
    """Admin for Voucher model with custom actions and inlines."""
    # Fields to show in the list view
    list_display = (
        'pk', 'voucher_type', 'created_at', 'account', 'voucher_amnt', 'state'
    )
    actions = [mark_as_applied]

    # Make some fields read-only to show metadata
    readonly_fields = ('voucher_amnt', 'notes', 'program_pause_flag', 'multiplier', 'created_at', 'updated_at')
    
    # Add filters in the right sidebar
    list_filter = ('voucher_type', 'account', 'state', 'created_at')
    
    # Add search functionality
    search_fields = ('voucher_type__name', 'account__name', 'notes') 
    
    inlines = [VoucherLogInline]
    
    def get_urls(self):
        """Add custom URLs for bulk voucher creation and reports."""
        urls = super().get_urls()
        custom_urls = [
            path(
                'bulk-create/',
                self.admin_site.admin_view(voucher_views.bulk_voucher_configure),
                name='bulk_voucher_configure'
            ),
            path(
                'bulk-create/preview/',
                self.admin_site.admin_view(voucher_views.bulk_voucher_preview),
                name='bulk_voucher_preview'
            ),
            path(
                'bulk-create/execute/',
                self.admin_site.admin_view(voucher_views.bulk_voucher_create),
                name='bulk_voucher_create'
            ),
            path(
                'redemption-report/',
                self.admin_site.admin_view(views_reports.voucher_redemption_report),
                name='voucher_redemption_report'
            ),
        ]
        return custom_urls + urls
    
    def changelist_view(self, request, extra_context=None):
        """Add bulk create button and reports link to voucher list."""
        extra_context = extra_context or {}
        extra_context['show_bulk_create_button'] = True
        extra_context['show_reports_link'] = True
        return super().changelist_view(request, extra_context=extra_context)


admin.site.register(VoucherSetting)
