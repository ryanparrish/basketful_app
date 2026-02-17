"""Tasks for program pause functionality."""
import logging
from celery import shared_task
from django.utils import timezone

from apps.voucher.models import Voucher
from apps.lifeskills.models import ProgramPause
from apps.lifeskills.utils import set_voucher_pause_state

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
            pp = ProgramPause.objects.all_pauses().get(id=program_pause_id)
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

    # Use utility function for actual voucher updates
    try:
        updated, skipped = set_voucher_pause_state(voucher_ids, activate=activate, multiplier=multiplier)
        logger.info(
            "[Task] Processed %d vouchers (updated=%d, skipped=%d) for ProgramPause ID=%s",
            len(voucher_ids),
            updated,
            skipped,
            program_pause_id
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
            if not hasattr(participant, 'accountbalance'):
                continue
            
            # Get vouchers with pause flag set
            vouchers_to_deactivate = participant.accountbalance.vouchers.filter(
                program_pause_flag=True,
                active=True
            )
            
            if vouchers_to_deactivate.exists():
                voucher_ids = list(
                    vouchers_to_deactivate.values_list('id', flat=True)
                )
                
                # Deactivate using utility
                updated, skipped = set_voucher_pause_state(voucher_ids, activate=False)
                
                logger.info(
                    "[Deactivation Task] Deactivated %d vouchers for "
                    "participant %s (ID=%s)",
                    updated,
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
    
    # Schedule final cleanup at pause_end as safety net
    try:
        pp = ProgramPause.objects.all_pauses().get(id=program_pause_id)
        now = timezone.now()
        
        if pp.pause_end and pp.pause_end > now:
            from datetime import timedelta
            final_cleanup_time = pp.pause_end + timedelta(minutes=5)
            
            logger.info(
                "[Deactivation Task] Scheduling final cleanup at %s "
                "(pause_end + 5min buffer)",
                final_cleanup_time
            )
            final_cleanup_after_pause_end.apply_async(
                args=[program_pause_id],
                eta=final_cleanup_time
            )
    except ProgramPause.DoesNotExist:
        logger.warning(
            "[Deactivation Task] ProgramPause ID=%s not found for final cleanup scheduling",
            program_pause_id
        )


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def final_cleanup_after_pause_end(self, program_pause_id):
    """
    Final cleanup task that runs after pause_end to ensure all vouchers are reset.
    Also marks the pause as archived.
    
    Args:
        program_pause_id (int): ID of the ProgramPause instance
    """
    try:
        pp = ProgramPause.objects.all_pauses().get(id=program_pause_id)
    except ProgramPause.DoesNotExist:
        logger.warning(
            "[Final Cleanup] ProgramPause ID=%s not found.",
            program_pause_id
        )
        return
    
    now = timezone.now()
    
    # Only run if pause has actually ended
    if pp.pause_end and pp.pause_end > now:
        logger.info(
            "[Final Cleanup] Pause hasn't ended yet (ends %s, now=%s). Skipping.",
            pp.pause_end, now
        )
        return
    
    # Find all vouchers still flagged
    flagged_vouchers = Voucher.objects.filter(
        program_pause_flag=True,
        active=True
    )
    
    if flagged_vouchers.exists():
        voucher_ids = list(flagged_vouchers.values_list('id', flat=True))
        updated, skipped = set_voucher_pause_state(voucher_ids, activate=False)
        
        logger.info(
            "[Final Cleanup] Reset %d vouchers for ProgramPause ID=%s",
            updated,
            program_pause_id
        )
    else:
        logger.info(
            "[Final Cleanup] No flagged vouchers found for ProgramPause ID=%s",
            program_pause_id
        )
    
    # Mark pause as archived
    if not pp.archived:
        pp.archived = True
        pp.archived_at = now
        pp.save(update_fields=['archived', 'archived_at'])
        logger.info(
            "[Final Cleanup] Marked ProgramPause ID=%s as archived",
            program_pause_id
        )


@shared_task(bind=True)
def cleanup_expired_pause_flags(self):
    """
    Daily task that finds expired pauses and cleans up any remaining flagged vouchers.
    Provides safety net for missed cleanups.
    """
    now = timezone.now()
    
    # Find all pauses (including archived) that have ended
    expired_pauses = ProgramPause.objects.all_pauses().filter(
        pause_end__lt=now
    )
    
    total_pauses_processed = 0
    total_vouchers_cleaned = 0
    
    for pause in expired_pauses:
        # Find vouchers still flagged
        flagged_vouchers = Voucher.objects.filter(
            program_pause_flag=True,
            active=True
        )
        
        if flagged_vouchers.exists():
            voucher_ids = list(flagged_vouchers.values_list('id', flat=True))
            updated, skipped = set_voucher_pause_state(voucher_ids, activate=False)
            
            if updated > 0:
                logger.info(
                    "[Daily Cleanup] Reset %d stale vouchers for ProgramPause ID=%s",
                    updated,
                    pause.id
                )
                total_vouchers_cleaned += updated
        
        # Mark as archived if not already
        if not pause.archived:
            pause.archived = True
            pause.archived_at = now
            pause.save(update_fields=['archived', 'archived_at'])
            logger.info(
                "[Daily Cleanup] Marked ProgramPause ID=%s as archived",
                pause.id
            )
        
        total_pauses_processed += 1
    
    logger.info(
        "[Daily Cleanup] Processed %d expired pauses, cleaned %d vouchers",
        total_pauses_processed,
        total_vouchers_cleaned
    )