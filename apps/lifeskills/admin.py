# lifeskills/admin.py
"""Admin configuration for lifeskills app."""
# Django imports
from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils.html import format_html
import re
# Local application imports
from .models import (
    ProgramPause, LifeskillsCoach,
    Program
)


def validate_address(address):
    """
    Validate address format.
    Expected format: Street Number + Street Name, City, State ZIP
    Example: 123 Main St, Springfield, IL 62701
    """
    # Pattern: number + street, city, state abbreviation + 5-digit zip
    pattern = r'^\d+\s+[\w\s]+,\s*[\w\s]+,\s*[A-Z]{2}\s+\d{5}(-\d{4})?$'
    if not re.match(pattern, address.strip()):
        raise ValidationError(
            'Address must be in format: '
            '"123 Main St, City, ST 12345" '
            '(Street Number, Street Name, City, State ZIP)'
        )


@admin.register(ProgramPause)
class ProgramPauseAdmin(admin.ModelAdmin):
    """Admin for ProgramPause with active pause notification."""
    list_display = ("reason", "pause_start", "pause_end", "is_active_gate")

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)

        all_pauses = ProgramPause.objects.all()
        active_pauses = [p for p in all_pauses if p.is_active_gate]
        if active_pauses:
            self.message_user(
                request,
                f"{active_pauses[0].reason} — This Pause Is Active",
                level=messages.INFO
            )

        return response


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    """
    Admin for Program with timezone-aware time display
    and address validation.
    """
    list_display = (
        'name',
        'MeetingDay',
        'display_meeting_time',
        'meeting_address',
        'created_at'
    )
    list_filter = ('MeetingDay',)
    search_fields = ('name', 'meeting_address')
    fieldsets = (
        ('Program Information', {
            'fields': ('name',)
        }),
        ('Meeting Schedule', {
            'fields': ('MeetingDay', 'meeting_time'),
            'description': (
                'Meeting time will be displayed in your browser\'s timezone'
            )
        }),
        ('Location', {
            'fields': ('meeting_address',),
            'description': 'Format: "123 Main St, City, ST 12345"'
        }),
    )

    def display_meeting_time(self, obj):
        """Display meeting time with timezone info."""
        if obj.meeting_time:
            return format_html(
                '<span title="Time will display in user\'s timezone">'
                '{}</span>',
                obj.meeting_time.strftime('%I:%M %p')
            )
        return '-'
    display_meeting_time.short_description = 'Meeting Time'
    display_meeting_time.admin_order_field = 'meeting_time'

    def save_model(self, request, obj, form, change):
        """Validate address format before saving."""
        try:
            validate_address(obj.meeting_address)
            super().save_model(request, obj, form, change)
            self.message_user(
                request,
                f'Program "{obj.name}" saved successfully.',
                messages.SUCCESS
            )
        except ValidationError as e:
            self.message_user(
                request,
                f'Error: {e.message}',
                messages.ERROR
            )
            raise

    class Media:
        js = ('admin/js/timezone_display.js',)


admin.site.register(LifeskillsCoach)
