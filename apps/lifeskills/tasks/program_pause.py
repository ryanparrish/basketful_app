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
            # Check if we're in the ordering window (11-14 days before pause starts)
            # or if the pause has already started
            days_until_start = (pp.pause_start - now).days if pp.pause_start else 0
            in_ordering_window = 11 <= days_until_start <= 14
            pause_started = pp.pause_start and pp.pause_start <= now
            
            if activate and pp.pause_start and not (in_ordering_window or pause_started):
                logger.info(
                    "[Task] Skipping activation for vouchers %s: "
                    "ProgramPause %s is outside ordering window "
                    "(starts %s, now=%s, days until start=%d).",
                    voucher_ids,
                    pp.id,
                    pp.pause_start,
                    now,
                    days_until_start
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


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def deactivate_expired_pause_vouchers(self, program_pause_id):
    """
    Smart self-rescheduling task that deactivates vouchers for participants
    whose order windows have closed.
    
    This task:
    1. Checks all active participants' order windows
    2. Deactivates vouchers for participants whose windows closed (with 5min buffer)
    3. Finds the next earliest window close time
    4. Reschedules itself for that time if more windows remain open
    
    Args:
        program_pause_id (int): ID of the ProgramPause instance
    """
    from datetime import timedelta
    from core.utils import can_place_order
    from apps.account.models import Participant
    
    try:
        pp = ProgramPause.objects.get(id=program_pause_id)
    except ProgramPause.DoesNotExist:
        logger.warning(
            "[Deactivation Task] ProgramPause ID=%s not found. "
            "Task will not reschedule.",
            program_pause_id
        )
        return
    
    now = timezone.now()
    buffer_minutes = 5
    
    logger.info(
        "[Deactivation Task] Running for ProgramPause ID=%s at %s",
        program_pause_id,
        now
    )
    
    participants_to_deactivate = []
    next_window_closes = []
    
    # Check all active participants
    for participant in Participant.objects.filter(
        active=True, 
        program__isnull=False
    ).select_related('program', 'accountbalance'):
        
        can_order, context = can_place_order(participant)
        window_closes = context.get('window_closes')
        
        if not window_closes:
            continue
        
        # Add buffer to window close time
        close_with_buffer = window_closes + timedelta(minutes=buffer_minutes)
        
        # If window closed (including buffer), mark for deactivation
        if close_with_buffer <= now:
            participants_to_deactivate.append(participant)
        else:
            # Track future close times for rescheduling
            next_window_closes.append(close_with_buffer)
    
    # Deactivate vouchers for participants whose windows have closed
    if participants_to_deactivate:
        logger.info(
            "[Deactivation Task] Deactivating vouchers for %d participants "
            "whose order windows have closed",
            len(participants_to_deactivate)
        )
        
        for participant in participants_to_deactivate:
            if not hasattr(participant, 'account'):
                continue
            
            # Get vouchers with pause flag set
            vouchers_to_deactivate = participant.account.vouchers.filter(
                program_pause_flag=True,
                active=True
            )
            
            if vouchers_to_deactivate.exists():
                voucher_ids = list(
                    vouchers_to_deactivate.values_list('id', flat=True)
                )
                
                # Deactivate these vouchers
                for voucher in vouchers_to_deactivate:
                    voucher.program_pause_flag = False
                    voucher.multiplier = 1
                    voucher.save(update_fields=['program_pause_flag', 'multiplier'])
                
                logger.info(
                    "[Deactivation Task] Deactivated %d vouchers for "
                    "participant %s (ID=%s)",
                    len(voucher_ids),
                    participant.name,
                    participant.id
                )
    else:
        logger.info(
            "[Deactivation Task] No participants with closed windows at this time"
        )
    
    # Reschedule if there are more windows to close
    if next_window_closes:
        earliest_next = min(next_window_closes)
        logger.info(
            "[Deactivation Task] Rescheduling for %s "
            "(next window close + %dmin buffer)",
            earliest_next,
            buffer_minutes
        )
        deactivate_expired_pause_vouchers.apply_async(
            args=[program_pause_id],
            eta=earliest_next
        )
    else:
        logger.info(
            "[Deactivation Task] All order windows closed. "
            "Task will not reschedule for ProgramPause ID=%s",
            program_pause_id
        )