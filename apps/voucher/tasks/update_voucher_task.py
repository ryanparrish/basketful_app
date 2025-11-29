# tasks/update_voucher_task.py

from celery import shared_task
import logging

from .helpers.voucher_input import normalize_voucher_ids
from .helpers.voucher_duration import program_pause_allows_execution
from .helpers.voucher_update import update_vouchers

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def update_voucher_flag(
    self, voucher_ids, multiplier=1, activate=False, program_pause_id=None
):
    """
    Thin orchestration wrapper: normalize → validate timing → update.
    """

    try:
        # Normalize inputs
        ids = normalize_voucher_ids(voucher_ids)
        if not ids:
            logger.info("[Task] No vouchers to update.")
            return

        # Check ProgramPause window
        if not program_pause_allows_execution(program_pause_id, activate):
            return

        # Perform the update
        updated_count = update_vouchers(ids, activate, multiplier)
        logger.info("[Task] %s/%s vouchers updated.",
                    updated_count, len(ids))

    except Exception as exc:
        logger.exception("[Task] Error updating vouchers.")
        raise self.retry(exc=exc)
