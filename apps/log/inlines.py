# food_orders/inlines.py
"""Admin inlines for OrderItems and VoucherLogs."""
# Django imports
from django.contrib import admin
from .models import VoucherLog


class VoucherLogInline(admin.TabularInline):
    """Inline admin for VoucherLogs, read-only."""
    model = VoucherLog
    fk_name = 'voucher'   # tells Django which FK to use
    fields = (
        'participant',
        'message',
        'log_type',
        'balance_before',
        'balance_after',
        'created_at',
    )
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True
