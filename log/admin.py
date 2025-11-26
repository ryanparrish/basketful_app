from django.contrib import admin
from .models import EmailLog, OrderValidationLog

@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    """Admin for EmailLog with read-only fields and search."""
    # Fields to display in the list view
    list_display = ('id', 'user', 'sent_at', 'email_type')

    # Fields that are read-only in the change form
    readonly_fields = ('user', 'email_type', 'sent_at')

    # Make searchable by these fields
    search_fields = ('user', 'email_type', 'sent_at')

    # Add filters in the right-hand sidebar
    list_filter = ('user', 'email_type')

    # Disable add and delete
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

admin.site.register(OrderValidationLog)
