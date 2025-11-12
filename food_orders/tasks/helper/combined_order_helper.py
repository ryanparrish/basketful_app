#food_orders/tasks/helper/combined_order_helper.py
from datetime import timedelta
from random import choice
from food_orders.models import CombinedOrder, Order
from django.db.models import Sum

def get_week_range(today):
    """Return the start and end of the current week (Mon–Sun)."""
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    return start_of_week, end_of_week


def weekly_parent_exists(program, start_date, end_date):
    """Check if a parent combined order already exists for this week."""
    return CombinedOrder.objects.filter(
        program=program,
        created_at__date__range=(start_date, end_date),
        is_parent=True,
    ).exists()


def get_weekly_orders(program, start_date, end_date):
    """Get all participant orders for the program in the week range."""
    return Order.objects.filter(
        account__participant__program=program,
        created_at__date__range=(start_date, end_date),
    )


def assign_orders_to_packers(program, orders, use_item_counts=False):
    """
    Assign orders to the static packers for the program.
    - 1 packer → all orders go to that packer
    - >1 packers → orders split evenly among them
    Returns a dict {packer: list of orders}.
    """
    packers = list(program.packers.all())
    if not packers:
        return {}

    # 1 packer → all orders assigned
    if len(packers) == 1:
        return {packers[0]: list(orders)}

    # >1 packers → split orders evenly
    # Optionally by total items
    if use_item_counts:
        orders = orders.annotate(total_items=Sum('order_items__quantity'))
    else:
        orders = orders.annotate(total_items=Sum('id') * 0 + 1)

    # Sort orders by total_items descending for better balance
    orders = sorted(orders, key=lambda o: o.total_items, reverse=True)

    # Split evenly among packers
    assignment = {packer: [] for packer in packers}
    for idx, order in enumerate(orders):
        packer = packers[idx % len(packers)]
        assignment[packer].append(order)

    return assignment


def create_child_combined_orders(program, weekly_orders, packer):
    """Create combined orders for each weekly order (children)."""
    child_orders = []
    for order in weekly_orders:
        combined_order = CombinedOrder.objects.create(
            program=program,
            packed_by=packer,
        )
        combined_order.orders.add(order)
        combined_order.summarized_data = combined_order.summarized_items_by_category()
        combined_order.save(update_fields=["summarized_data"])
        child_orders.append(combined_order)
    return child_orders


def create_parent_combined_order(program, child_combined_orders, packer):
    """Create parent combined order that aggregates all child combined orders."""
    parent_order = CombinedOrder.objects.create(
        program=program,
        packed_by=packer,
        is_parent=True,
    )

    all_orders = Order.objects.filter(combined_orders__in=child_combined_orders).distinct()
    parent_order.orders.set(all_orders)
    parent_order.summarized_data = parent_order.summarized_items_by_category()
    parent_order.save(update_fields=["summarized_data"])
    return parent_order
