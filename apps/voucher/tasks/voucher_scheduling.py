
import sys
import logging
from django.utils import timezone
from update_voucher_task import update_voucher_flag
# Configure logger
logger = logging.getLogger(__name__)


def schedule_voucher_tasks(vouchers, activate_time=None, deactivate_time=None):
    """
    Schedule activation and deactivation tasks for a set of vouchers.
    """
    voucher_ids = list(vouchers.values_list("id", flat=True))
    logger.debug("Voucher IDs affected: %s", voucher_ids)

    now = timezone.now()

    # Activation
    if activate_time:
        if activate_time > now:
            logger.debug("Scheduling activation at %s", activate_time)
            update_voucher_flag.apply_async(
                args=[voucher_ids], kwargs={"multiplier": 2, "activate": True}, eta=activate_time
            )
        else:
            logger.debug("Activating vouchers immediately.")
            update_voucher_flag.delay(voucher_ids, multiplier=2, activate=True)

    # Deactivation
    if deactivate_time and "test" not in sys.argv:
        if deactivate_time > now:
            logger.debug("Scheduling deactivation at %s", deactivate_time)
            update_voucher_flag.apply_async(
                args=[voucher_ids], kwargs={"multiplier": 1, "activate": False}, eta=deactivate_time
            )
        elif deactivate_time <= now:
            logger.debug("Deactivating vouchers immediately.")
            update_voucher_flag.delay(voucher_ids, multiplier=1, activate=False)
    else:
        logger.debug("Skipping deactivation scheduling in test mode.")