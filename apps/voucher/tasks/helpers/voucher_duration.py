# tasks/helpers/voucher_duration.py
from django.utils import timezone
import logging

from lifeskills.models import ProgramPause

logger = logging.getLogger(__name__)


def program_pause_allows_execution(program_pause_id, activate):
    """
    Returns True/False whether the task should run now.
    Provides all skip-level logging.
    """
    if not program_pause_id:
        return True

    now = timezone.now()

    try:
        pp = ProgramPause.objects.get(id=program_pause_id)
    except ProgramPause.DoesNotExist:
        logger.warning("[Task] ProgramPause %s not found; running anyway.", program_pause_id)
        return True

    # Activation must wait for pause_start
    if activate and pp.pause_start and pp.pause_start > now:
        logger.info(
            "[Task] Skipping activation: ProgramPause %s starts at %s (now=%s)",
            pp.id, pp.pause_start, now
        )
        return False

    # Deactivation must wait for pause_end
    if not activate and pp.pause_end and pp.pause_end > now:
        logger.info(
            "[Task] Skipping deactivation: ProgramPause %s ends at %s (now=%s)",
            pp.id, pp.pause_end, now
        )
        return False

    return True
