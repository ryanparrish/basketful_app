from django.contrib import admin, messages
from .models import Voucher, VoucherSetting
from log.inlines import VoucherLogInline


@admin.action(description="Mark selected vouchers as Applied")
def mark_as_applied(modeladmin, request, queryset):
    """Mark selected vouchers as Applied."""
    updated = queryset.update(state='applied')
    if updated:
        messages.success(request, f"{updated} voucher(s) marked as Applied.")
    else:
        messages.warning(request, "No vouchers were updated.")


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    """Admin for Voucher model with custom actions and inlines."""
    # Fields to show in the list view
    list_display = (
        'pk', 'voucher_type', 'created_at', 'account', 'voucher_amnt', 'state'
    )
    actions = [mark_as_applied]

    # Make some fields read-only
    readonly_fields = ('voucher_amnt', 'notes')
    
    # Fields to hide from the admin form entirely
    exclude = ('program_pause_flag', 'multiplier')
    
    # Add filters in the right sidebar
    list_filter = ('voucher_type', 'account', 'state', 'created_at')
    
    # Add search functionality
    search_fields = ('voucher_type__name', 'account__name', 'notes') 
    
    inlines = [VoucherLogInline]


admin.site.register(VoucherSetting)
