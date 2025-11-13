# food_orders/tasks/helper/combined_order_helper.py
import logging
from datetime import timedelta
from typing import Dict, List, Optional

from django.db.models import Sum
from django.core.mail import mail_admins

from food_orders.models import CombinedOrder, Order, Program
from django.core.exceptions import ValidationError


logger = logging.getLogger(__name__)

# ─────────────────────────────
# Core Helpers
# ─────────────────────────────

def get_week_range(today) -> tuple:
    """Return the start and end of the current week (Mon–Sun)."""
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    return start_of_week, end_of_week


def weekly_parent_exists(program: Program, start_date, end_date) -> bool:
    """Check if a parent combined order already exists for this week."""
    exists = CombinedOrder.objects.filter(
        program=program,
        created_at__date__range=(start_date, end_date),
        is_parent=True,
    ).exists()
    logger.debug(f"Weekly parent exists for {program.name}: {exists}")
    return exists


def get_weekly_orders(program: Program, start_date, end_date):
    """
    Get all participant orders for the program in the week range.
    Raises ValidationError if no orders are found.
    """
    orders = Order.objects.filter(
        account__participant__program=program,
        created_at__date__range=(start_date, end_date),
    )
    
    order_count = orders.count()
    logger.debug(f"Fetched {order_count} orders for {program.name}")

    if order_count == 0:
        raise ValidationError(f"No weekly orders found for program {program.name}")

    return orders

def validate_program_for_week(program: Program, start_of_week, end_of_week):
    """Raise ValidationError if program cannot be processed for the week."""
    if weekly_parent_exists(program, start_of_week, end_of_week):
        raise ValidationError(f"Weekly parent order already exists for {program.name}")

    weekly_orders = get_weekly_orders(program, start_of_week, end_of_week)
    if not weekly_orders.exists():
        raise ValidationError(f"No weekly orders found for {program.name}")

    if not program.packers.exists():
        raise ValidationError(f"No packers assigned to program {program.name}")

    return weekly_orders

def validate_packers_exist(program: Program):
    """Raise ValidationError if no packers are assigned to the program."""
    if not program.packers.exists():
        raise ValidationError(f"No packers assigned to program {program.name}")
    logger.debug(f"{program.packers.count()} packers found for {program.name}")


def assign_orders_to_packers(
    program: Program, orders, use_item_counts: bool = False
) -> Dict[Program, List[Order]]:
    """
    Assign orders evenly among program packers.
    Raises ValidationError if no packers exist.
    """
    # Validate packers first
    validate_packers_exist(program)
    
    packers = list(program.packers.all())

    # Annotate orders for sorting
    if use_item_counts:
        orders = orders.annotate(total_items=Sum('order_items__quantity'))
    else:
        orders = orders.annotate(total_items=Sum('id') * 0 + 1)

    # Sort descending to balance assignments
    orders = sorted(orders, key=lambda o: o.total_items, reverse=True)

    # Split orders evenly
    assignment = {packer: [] for packer in packers}
    for idx, order in enumerate(orders):
        packer = packers[idx % len(packers)]
        assignment[packer].append(order)

    logger.debug(f"Orders assigned to {len(assignment)} packers for {program.name}")
    return assignment


def create_child_combined_orders(program: Program, orders: List[Order], packer) -> List[CombinedOrder]:
    """Create child combined orders for a packer."""
    child_orders = []
    for order in orders:
        combined_order = CombinedOrder.objects.create(
            program=program,
            packed_by=packer,
        )
        combined_order.orders.add(order)
        combined_order.summarized_data = combined_order.summarized_items_by_category()
        combined_order.save(update_fields=["summarized_data"])
        child_orders.append(combined_order)

    logger.debug(f"Created {len(child_orders)} child orders for packer {packer} in {program.name}")
    return child_orders


def create_parent_combined_order(program: Program, child_orders: List[CombinedOrder], packer=None) -> CombinedOrder:
    """Create parent combined order that aggregates all child orders."""
    parent_order = CombinedOrder.objects.create(
        program=program,
        packed_by=packer,
        is_parent=True,
    )
    all_orders = Order.objects.filter(combined_orders__in=child_orders).distinct()
    parent_order.orders.set(all_orders)
    parent_order.summarized_data = parent_order.summarized_items_by_category()
    parent_order.save(update_fields=["summarized_data"])

    logger.debug(f"Created parent order {parent_order.id} for {program.name} with {len(child_orders)} children")
    return parent_order


# ─────────────────────────────
# Modular Program Processing
# ─────────────────────────────

def process_program(program: Program, start_of_week, end_of_week) -> bool:
    """Handle weekly combined order creation for a single program with validations."""
    logger.info(f"Processing program: {program.name} (ID: {program.id})")

    try:
        weekly_orders = validate_program_for_week(program, start_of_week, end_of_week)

        # Assign orders to packers
        order_assignment = assign_orders_to_packers(program, weekly_orders, use_item_counts=True)
        if not order_assignment:
            # This should never happen if validation passed
            raise ValidationError(f"Failed to assign orders to packers for {program.name}")

        # Create child combined orders
        child_orders: List[CombinedOrder] = []
        for packer, orders_for_packer in order_assignment.items():
            child_orders.extend(create_child_combined_orders(program, orders_for_packer, packer))

        # Create parent combined order
        create_parent_combined_order(program, child_orders, packer=None)

        logger.info(f"Successfully created combined orders for {program.name}")
        return True

    except ValidationError as ve:
        # Log validation errors but do not send email alerts
        logger.warning(f"Validation skipped for program {program.name}: {ve}")
        return False

    except Exception as e:
        # Log unexpected errors and notify admins
        logger.exception(f"Error processing program {program.name}: {e}")
        mail_admins(
            subject=f"[Basketful] Weekly order creation failed for {program.name}",
            message=str(e),
        )
        return False


def process_all_programs(start_of_week, end_of_week) -> tuple[int, int]:
    """Process all programs and return counts: (processed, created)."""
    processed, created = 0, 0
    for program in Program.objects.all():
        processed += 1
        if process_program(program, start_of_week, end_of_week):
            created += 1

    logger.info(f"Processed {processed} programs, created orders for {created}")
    return processed, created
