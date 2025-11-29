
# lifeskills/signals.py
"""Signals for lifeskills app to handle ProgramPause events."""
# Standard library imports
import logging
# Django imports
from django.db.models.signals import post_save
from django.dispatch import receiver
# First-party imports
from voucher.models import Voucher
from voucher.tasks.voucher_scheduling import schedule_voucher_tasks
# Local imports
from .models import ProgramPause
logger = logging.getLogger(__name__)

@receiver(post_save, sender=ProgramPause)
def handle_program_pause(sender, instance, created, **kwargs):
    """
    Signal to handle ProgramPause events and delegate voucher updates.
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