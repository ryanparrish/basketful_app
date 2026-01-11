"""Tasks for program pause functionality."""
import logging
from celery import shared_task
from django.utils import timezone

from apps.voucher.models import Voucher
from apps.lifeskills.models import ProgramPause

logger = logging.getLogger(__name__)


def update_voucher_flag(program_pause_id):
    """
    Wrapper function to update voucher flags based on a ProgramPause.
    This is called synchronously (not as a Celery task) for testing.
    
    Args:
        program_pause_id (int): ID of the ProgramPause instance.
    """
    try:
        pp = ProgramPause.objects.get(id=program_pause_id)
    except ProgramPause.DoesNotExist:
        logger.warning(
            "ProgramPause with ID=%s not found", program_pause_id
        )
        return
    
    # Get all active vouchers with active accounts
    vouchers = Voucher.objects.filter(active=True, account__active=True)
    
    if not vouchers.exists():
        logger.info(
            "No active vouchers to update for ProgramPause ID=%s",
            program_pause_id
        )
        return
    
    # Update vouchers to set program_pause_flag=True and multiplier=2
    voucher_ids = list(vouchers.values_list('id', flat=True))
    
    for voucher in vouchers:
        voucher.program_pause_flag = True
        voucher.multiplier = 2
        voucher.save(update_fields=['program_pause_flag', 'multiplier'])
        logger.info(
            "Voucher ID=%s updated: program_pause_flag=True, multiplier=2",
            voucher.id
        )
    
    logger.info(
        "Updated %d vouchers for ProgramPause ID=%s",
        len(voucher_ids),
        program_pause_id
    )


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def update_voucher_flag_task(
    self, voucher_ids, multiplier=1, activate=False, program_pause_id=None
):
    """
    Idempotent task to update a list of vouchers safely and log changes.

    Args:
        voucher_ids (list[int] or int): IDs of vouchers to update.
        multiplier (int): Multiplier to apply.
        activate (bool): True -> set program_pause_flag, False -> clear it.
        program_pause_id (int): Optional ProgramPause ID for validation.
    """
    if not voucher_ids:
        logger.info("[Task] No vouchers to update.")
        return

    # --- Ensure voucher_ids is always iterable ---
    if isinstance(voucher_ids, int):
        voucher_ids = [voucher_ids]
    elif not hasattr(voucher_ids, '__iter__'):
        voucher_ids = list(voucher_ids)

    now = timezone.now()

    # --- Duration check (protects against premature toggles) ---
    if program_pause_id:
        try:
            pp = ProgramPause.objects.get(id=program_pause_id)
        except ProgramPause.DoesNotExist:
            logger.warning(
                "[Task] ProgramPause %s not found; skipping duration check.",
                program_pause_id
            )
            pp = None

        if pp:
            if activate and pp.pause_start and pp.pause_start > now:
                logger.info(
                    "[Task] Skipping activation for vouchers %s: "
                    "ProgramPause %s has not started yet "
                    "(starts %s, now=%s).",
                    voucher_ids,
                    pp.id,
                    pp.pause_start,
                    now
                )
                return
            if not activate and pp.pause_end and pp.pause_end > now:
                logger.info(
                    "[Task] Skipping deactivation for vouchers %s: "
                    "ProgramPause %s has not ended yet (ends %s, now=%s).",
                    voucher_ids,
                    pp.id,
                    pp.pause_end,
                    now
                )
                return

    try:
        vouchers = Voucher.objects.filter(id__in=voucher_ids)

        for voucher in vouchers:
            target_flag = activate
            target_multiplier = multiplier if activate else 1
            updated_fields = []

            # --- Compare current state vs target state ---
            if voucher.program_pause_flag != target_flag:
                voucher.program_pause_flag = target_flag
                updated_fields.append("program_pause_flag")
            if voucher.multiplier != target_multiplier:
                voucher.multiplier = target_multiplier
                updated_fields.append("multiplier")

            if updated_fields:
                voucher.save(update_fields=updated_fields)
                logger.info(
                    (
                        "[Task] Voucher ID=%s updated: "
                        "program_pause_flag=%s, multiplier=%s"
                    ),
                    voucher.id,
                    voucher.program_pause_flag,
                    voucher.multiplier
                )
            else:
                # --- Explicitly log idempotent skip ---
                logger.info(
                    (
                        "[Task] Voucher ID=%s already up-to-date. "
                        "(program_pause_flag=%s, multiplier=%s)"
                    ),
                    voucher.id,
                    voucher.program_pause_flag,
                    voucher.multiplier
                )
                
    except Exception as exc:
        logger.exception("[Task] Error updating vouchers: %s", voucher_ids)
        raise self.retry(exc=exc)
