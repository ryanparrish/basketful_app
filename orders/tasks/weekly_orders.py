# food_orders/tasks/weekly_orders.py
import logging
# third party imports
from celery import shared_task
# local imports
from django.utils import timezone
from .helper.combined_order_helper import get_week_range, process_all_programs

logger = logging.getLogger(__name__)


@shared_task
def create_weekly_combined_orders():
    """
    Celery task: create weekly combined orders for each program,
    with detailed modular logging.
    """
    logger.info("Starting weekly combined order creation task.")

    today = timezone.localdate()
    start_of_week, end_of_week = get_week_range(today)
    logger.debug("Week range calculated: %s to %s", start_of_week, end_of_week)

    processed, created = process_all_programs(start_of_week, end_of_week)

    logger.info(
        "Weekly combined order creation completed: processed=%s, created=%s",
        processed,
        created,
    )
