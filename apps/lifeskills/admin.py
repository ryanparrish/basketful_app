# lifeskills/admin.py
"""Admin configuration for lifeskills app."""
# Django imports
from django.contrib import admin
from django.contrib import messages
# Local application imports
from .models import (
    ProgramPause, LifeskillsCoach,
    Program
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


admin.site.register(Program)
admin.site.register(LifeskillsCoach)