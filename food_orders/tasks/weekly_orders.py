from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from food_orders.models import Program
from food_orders.tasks.helper.combined_order_helper import (
    get_week_range,
    weekly_parent_exists,
    get_weekly_orders,
    create_child_combined_orders,
    create_parent_combined_order,
    assign_orders_to_packers,

)
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from food_orders.models import Program


@shared_task
def create_weekly_combined_orders():
    """Celery task: create weekly combined orders for each program."""
    today = timezone.localdate()
    start_of_week, end_of_week = get_week_range(today)

    for program in Program.objects.all():
        try:
            # Skip if parent combined order already exists
            if weekly_parent_exists(program, start_of_week, end_of_week):
                continue

            weekly_orders = get_weekly_orders(program, start_of_week, end_of_week)
            if not weekly_orders.exists():
                continue

            # Assign orders to packers according to the program's static packers
            order_assignment = assign_orders_to_packers(program, weekly_orders, use_item_counts=True)

            # Step 1: create child combined orders per packer
            child_orders = []
            for packer, orders_for_packer in order_assignment.items():
                child_combined_orders = create_child_combined_orders(program, orders_for_packer, packer)
                child_orders.extend(child_combined_orders)

            # Step 2: create parent combined order aggregating all child orders
            # The parent order's packed_by can be left null, or set to a default if needed
            create_parent_combined_order(program, child_orders, packed_by=None)

        except Exception as e:
            # Optional: log errors per program for debugging
            from django.core.mail import mail_admins
            from django.utils.log import getLogger
            logger = getLogger(__name__)
            logger.exception(f"Error creating weekly combined orders for {program}: {e}")
            mail_admins(
                subject=f"[Basketful] Weekly order creation failed for {program}",
                message=str(e),
            )
