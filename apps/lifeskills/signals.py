# lifeskills/signals.py
"""Signals for lifeskills app to handle ProgramPause events."""
# Standard library imports
import logging
# Django imports
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
# First-party imports
from voucher.models import Voucher
from voucher.tasks.voucher_scheduling import schedule_voucher_tasks
from apps.log.logging import VoucherLogger
from apps.lifeskills.tasks.program_pause import (
    update_voucher_flag_task,
    deactivate_expired_pause_vouchers,
)
# Local imports
from .models import ProgramPause

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ProgramPause)
def handle_program_pause(sender, instance, created, **kwargs):
    """
    Signal to handle ProgramPause events and delegate voucher updates.
    
    If pause is created within the 11-14 day ordering window, immediately
    flag vouchers with appropriate multiplier and schedule smart deactivation.
    Otherwise, schedule activation for pause_start time.
    """
    logger.debug("=== Signal Triggered for ProgramPause ID=%s ===", instance.id)
    logger.debug(
        "Created=%s, pause_start=%s, pause_end=%s",
        created,
        instance.pause_start,
        instance.pause_end,
    )

    if getattr(instance, "_skip_signal", False):
        logger.debug("Skip signal flag detected; exiting to avoid recursion")
        return

    # Only active vouchers with active accounts
    vouchers = Voucher.objects.filter(active=True, account__active=True)
    if not vouchers.exists():
        logger.debug("No active vouchers found; exiting signal.")
        return

    now = timezone.now()
    days_until_start = (instance.pause_start - now).days

    # Check if we're in the 11-14 day ordering window
    if 11 <= days_until_start <= 14:
        logger.info(
            "ProgramPause ID=%s is within 11-14 day ordering window "
            "(starts in %d days). Flagging vouchers immediately.",
            instance.id,
            days_until_start
        )
        
        # Calculate appropriate multiplier based on duration
        multiplier = ProgramPause.calculate_multiplier_for_duration(
            instance.pause_start, instance.pause_end
        )
        
        # Immediately activate vouchers with the calculated multiplier
        voucher_ids = list(vouchers.values_list('id', flat=True))
        update_voucher_flag_task.delay(
            voucher_ids, 
            multiplier=multiplier, 
            activate=True,
            program_pause_id=instance.id
        )
        
        logger.info(
            "Flagged %d vouchers with multiplier=%d for ProgramPause ID=%s",
            len(voucher_ids),
            multiplier,
            instance.id
        )
        
        # Schedule smart deactivation task
        # Start checking after the earliest participant's order window closes
        from core.utils import get_next_class_datetime
        from apps.account.models import Participant
        
        earliest_close = None
        for participant in Participant.objects.filter(active=True, program__isnull=False):
            next_class = get_next_class_datetime(participant)
            if next_class:
                # Window closes at class time (or hours_before_close if configured)
                from core.models import OrderWindowSettings
                settings = OrderWindowSettings.get_settings()
                from datetime import timedelta
                window_closes = next_class - timedelta(hours=settings.hours_before_close)
                # Add 5-minute buffer
                close_with_buffer = window_closes + timedelta(minutes=5)
                
                if earliest_close is None or close_with_buffer < earliest_close:
                    earliest_close = close_with_buffer
        
        if earliest_close and earliest_close > now:
            logger.info(
                "Scheduling deactivation task for ProgramPause ID=%s at %s "
                "(earliest window close + 5min buffer)",
                instance.id,
                earliest_close
            )
            deactivate_expired_pause_vouchers.apply_async(
                args=[instance.id],
                eta=earliest_close
            )
        else:
            logger.warning(
                "Could not determine earliest window close time for ProgramPause ID=%s",
                instance.id
            )
    else:
        # Outside ordering window - use original scheduling logic
        logger.info(
            "ProgramPause ID=%s is outside 11-14 day window (starts in %d days). "
            "Scheduling tasks for future execution.",
            instance.id,
            days_until_start
        )
        try:
            schedule_voucher_tasks(
                vouchers,
                activate_time=instance.pause_start,
                deactivate_time=instance.pause_end,
            )
            logger.debug(
                "Tasks scheduled successfully for ProgramPause ID=%s affecting %d vouchers",
                instance.id,
                vouchers.count(),
            )
        except Exception as e:
            for voucher in vouchers:
                VoucherLogger.error(
                    voucher.account.participant,
                    f"Unexpected error in ProgramPause signal: {e}",
                    voucher=voucher,
                )
            raise

    logger.debug("=== End of Signal ===\n")