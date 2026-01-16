# food_orders/taskslogs.py
"""Tasks for logging voucher applications and updating voucher flags."""
# Standard library imports
import logging
# Third-party imports
from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model
# First-party imports
from apps.orders.models import Order 
from apps.voucher.models import Voucher
from apps.log.models import VoucherLog
from apps.account.models import Participant
from apps.lifeskills.models import ProgramPause

# Create a logger for this module
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)  # or DEBUG if you want more detail

# Optional: add a console handler if one doesn’t exist
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

User = get_user_model()


@shared_task
def log_voucher_application_task(
    order_id, voucher_id, participant_id, applied_amount, remaining
):
    """
    Task to log the application of a voucher to an order.
    """
    # Fetch related objects
    # If Order does not have a default manager, use the appropriate manager or method
    order = Order.objects.get(id=order_id)  # Ensure Order is a Django model
    voucher = Voucher.objects.get(id=voucher_id)
    participant = Participant.objects.get(id=participant_id)

    # Ensure numeric values are never None
    applied_amount = float(applied_amount or 0.0)
    remaining = float(remaining or 0.0)

    # Determine note type
    note_type = "Fully used" if applied_amount == voucher.voucher_amnt else "Partially used"

    # Build log message
    message = (
        f"{note_type} voucher {voucher.id} "
        f"for ${applied_amount:.2f}, remaining amount needed: ${remaining:.2f}"
    )

    # Create log entry
    VoucherLog.objects.create(
        order=order,
        voucher=voucher,
        participant=participant,
        applied_amount=applied_amount,
        remaining=remaining,
        message=message,
        log_type=VoucherLog.INFO,
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
        program_pause_id (int): Optional ProgramPause ID for duration validation.
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
                    "ProgramPause %s has not started yet (starts %s, now=%s).",
                    voucher_ids,
                    pp.id,
                    pp.pause_start,
                    now
                )
                return
            if not activate and pp.pause_end and pp.pause_end > now:
                logger.info(
                    "[Task] Skipping deactivation for vouchers %s: ProgramPause %s "
                    "has not ended yet (ends %s, now=%s).",
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
                        "[Task] Voucher ID=%s updated: program_pause_flag=%s, "
                        "multiplier=%s"
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


def update_voucher_flag(
    voucher_ids=None, multiplier=1, activate=False, program_pause_id=None
):
    """
    Synchronous function to update voucher flags.
    Can be called with either:
    - voucher_ids, multiplier, activate (for direct voucher updates)
    - program_pause_id alone (for program pause-based updates)
    
    Args:
        voucher_ids (list[int] or int): IDs of vouchers to update.
        multiplier (int): Multiplier to apply.
        activate (bool): True -> set program_pause_flag, False -> clear it.
        program_pause_id (int): ID of the ProgramPause instance.
    """
    # If ONLY program_pause_id is provided (no voucher_ids), use new logic
    if program_pause_id is not None and voucher_ids is None:
        try:
            pp = ProgramPause.objects.get(id=program_pause_id)
        except ProgramPause.DoesNotExist:
            logger.warning(
                "ProgramPause with ID=%s not found", program_pause_id
            )
            return
        
        # Get all active vouchers with active accounts
        vouchers = Voucher.objects.filter(
            active=True, account__active=True
        )
        
        if not vouchers.exists():
            logger.info(
                "No active vouchers to update for ProgramPause ID=%s",
                program_pause_id
            )
            return
        
        # Update vouchers to set program_pause_flag=True and multiplier=2
        voucher_ids_list = list(vouchers.values_list('id', flat=True))
        
        for voucher in vouchers:
            voucher.program_pause_flag = True
            voucher.multiplier = 2
            voucher.save(update_fields=['program_pause_flag', 'multiplier'])
            logger.info(
                "Voucher ID=%s updated: program_pause_flag=True, "
                "multiplier=2",
                voucher.id
            )
        
        logger.info(
            "Updated %d vouchers for ProgramPause ID=%s",
            len(voucher_ids_list),
            program_pause_id
        )
        return
    
    # Otherwise, use the old logic with voucher_ids, multiplier, activate
    if not voucher_ids:
        logger.info("No vouchers to update.")
        return

    # Ensure voucher_ids is always iterable
    if isinstance(voucher_ids, int):
        voucher_ids = [voucher_ids]
    elif not hasattr(voucher_ids, '__iter__'):
        voucher_ids = list(voucher_ids)

    now = timezone.now()

    # Duration check for program pause
    if program_pause_id:
        try:
            pp = ProgramPause.objects.get(id=program_pause_id)
        except ProgramPause.DoesNotExist:
            logger.warning(
                "ProgramPause %s not found; skipping duration check.",
                program_pause_id
            )
            pp = None

        if pp:
            if activate and pp.pause_start and pp.pause_start > now:
                logger.info(
                    "Skipping activation for vouchers %s: "
                    "ProgramPause %s has not started yet (starts %s, now=%s).",
                    voucher_ids,
                    pp.id,
                    pp.pause_start,
                    now
                )
                return
            if not activate and pp.pause_end and pp.pause_end > now:
                logger.info(
                    "Skipping deactivation for vouchers %s: ProgramPause %s "
                    "has not ended yet (ends %s, now=%s).",
                    voucher_ids,
                    pp.id,
                    pp.pause_end,
                    now
                )
                return

    vouchers = Voucher.objects.filter(id__in=voucher_ids)

    for voucher in vouchers:
        target_flag = activate
        target_multiplier = multiplier if activate else 1
        updated_fields = []

        # Compare current state vs target state
        if voucher.program_pause_flag != target_flag:
            voucher.program_pause_flag = target_flag
            updated_fields.append("program_pause_flag")
        if voucher.multiplier != target_multiplier:
            voucher.multiplier = target_multiplier
            updated_fields.append("multiplier")

        if updated_fields:
            voucher.save(update_fields=updated_fields)
            logger.info(
                "Voucher ID=%s updated: program_pause_flag=%s, multiplier=%s",
                voucher.id,
                voucher.program_pause_flag,
                voucher.multiplier
            )
        else:
            # Explicitly log idempotent skip
            logger.info(
                "Voucher ID=%s already up-to-date. "
                "(program_pause_flag=%s, multiplier=%s)",
                voucher.id,
                voucher.program_pause_flag,
                voucher.multiplier
            )
