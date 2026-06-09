
import sys
import logging
from django.utils import timezone
from django.utils.timezone import is_naive, make_aware
from apps.lifeskills.tasks.program_pause import update_voucher_flag_task
# Configure logger
logger = logging.getLogger(__name__)


def schedule_voucher_tasks(vouchers, activate_time=None, deactivate_time=None):
    """
    Schedule activation and deactivation tasks for a set of vouchers.
    """
    voucher_ids = list(vouchers.values_list("id", flat=True))
    logger.debug("Voucher IDs affected: %s", voucher_ids)

    # Defensive: comparing naive datetimes against timezone.now() raises TypeError.
    # Treat naive inputs as local time (consistent with how the serializer handles them).
    if activate_time and is_naive(activate_time):
        logger.warning(
            "schedule_voucher_tasks received a naive activate_time (%s); "
            "converting to aware. Pass a timezone-aware datetime to avoid this.",
            activate_time,
        )
        activate_time = make_aware(activate_time)
    if deactivate_time and is_naive(deactivate_time):
        logger.warning(
            "schedule_voucher_tasks received a naive deactivate_time (%s); "
            "converting to aware. Pass a timezone-aware datetime to avoid this.",
            deactivate_time,
        )
        deactivate_time = make_aware(deactivate_time)

    now = timezone.now()

    # Activation
    if activate_time:
        if activate_time > now:
            logger.debug("Scheduling activation at %s", activate_time)
            update_voucher_flag_task.apply_async(
                args=[voucher_ids], kwargs={"multiplier": 2, "activate": True}, eta=activate_time
            )
        else:
            logger.debug("Activating vouchers immediately.")
            update_voucher_flag_task.delay(voucher_ids, multiplier=2, activate=True)

    # Deactivation
    if deactivate_time and "test" not in sys.argv:
        if deactivate_time > now:
            logger.debug("Scheduling deactivation at %s", deactivate_time)
            update_voucher_flag_task.apply_async(
                args=[voucher_ids], kwargs={"multiplier": 1, "activate": False}, eta=deactivate_time
            )
        elif deactivate_time <= now:
            logger.debug("Deactivating vouchers immediately.")
            update_voucher_flag_task.delay(voucher_ids, multiplier=1, activate=False)
    else:
        logger.debug("Skipping deactivation scheduling in test mode.")