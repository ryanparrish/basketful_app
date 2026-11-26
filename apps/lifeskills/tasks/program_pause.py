"""Tasks for program pause functionality."""
import logging
from celery import shared_task
from django.utils import timezone

from apps.lifeskills.models import ProgramPause

logger = logging.getLogger(__name__)


@shared_task
def archive_ended_pauses():
    """
    Nightly: archive pauses whose pause_end has passed.

    Pauses only affect anything while in their double-week window (read
    live by apps.lifeskills.utils.active_pause), so archiving is
    bookkeeping that keeps ended pauses out of the active list.
    """
    now = timezone.now()
    archived_count = 0
    for pause in ProgramPause.objects.filter(pause_end__lt=now):  # excludes archived
        pause.archived = True
        pause.archived_at = now
        pause.save(update_fields=['archived', 'archived_at'])
        archived_count += 1

    logger.info("[Daily Cleanup] Archived %d ended pauses", archived_count)
    return archived_count
