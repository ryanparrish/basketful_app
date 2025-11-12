# food_orders/logs.py
from celery import shared_task
from django.utils import timezone

from django.contrib.auth import get_user_model
import logging
from ..models import (
    Voucher, 
    ProgramPause,
    VoucherLog, 
    Order, 
    Participant,
)

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
def log_voucher_application_task(order_id, voucher_id, participant_id, applied_amount, remaining):
    # Fetch related objects
    order = Order.objects.get(id=order_id)
    voucher = Voucher.objects.get(id=voucher_id)
    participant = Participant.objects.get(id=participant_id)

    # Ensure numeric values are never None
    applied_amount = float(applied_amount or 0.0)
    remaining = float(remaining or 0.0)

    # Determine note type
    note_type = "Fully" if applied_amount == voucher.voucher_amnt else "Partially"

    # Build log message
    message = (
        f"{note_type} used voucher {voucher.id} "
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
def update_voucher_flag(self, voucher_ids, multiplier=1, activate=False, program_pause_id=None):
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
            logger.warning(f"[Task] ProgramPause {program_pause_id} not found; skipping duration check.")
            pp = None

        if pp:
            if activate and pp.pause_start and pp.pause_start > now:
                logger.info(
                    f"[Task] Skipping activation for vouchers {voucher_ids}: "
                    f"ProgramPause {pp.id} has not started yet (starts {pp.pause_start}, now={now})."
                )
                return
            if not activate and pp.pause_end and pp.pause_end > now:
                logger.info(
                    f"[Task] Skipping deactivation for vouchers {voucher_ids}: "
                    f"ProgramPause {pp.id} has not ended yet (ends {pp.pause_end}, now={now})."
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
                    f"[Task] Voucher ID={voucher.id} updated: "
                    f"program_pause_flag={voucher.program_pause_flag}, "
                    f"multiplier={voucher.multiplier}"
                )
            else:
                # --- Explicitly log idempotent skip ---
                logger.info(
                    f"[Task] Voucher ID={voucher.id} already up-to-date. "
                    f"(program_pause_flag={voucher.program_pause_flag}, multiplier={voucher.multiplier})"
                )

    except Exception as exc:
        logger.exception(f"[Task] Error updating vouchers: {voucher_ids}")
        raise self.retry(exc=exc)
