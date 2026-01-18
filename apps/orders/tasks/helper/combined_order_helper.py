# food_orders/tasks/helper/combined_order_helper.py
"""Helper functions for weekly combined order creation task."""
# Standard library imports
import logging
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
# Third party imports
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.core.mail import mail_admins
# First-party imports
from apps.lifeskills.models import Program
# Local imports
from apps.orders.models import CombinedOrder, Order, PackingList, PackingSplitRule


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
    # Cast to Any to satisfy static type checkers that may not recognize Django managers
    exists = CombinedOrder.objects.filter(
        program=program,
        created_at__date__range=(start_date, end_date),
        is_parent=True,
    ).exists()
    logger.debug("Weekly parent exists for %s: %s", program.name, exists)
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
    logger.debug("Fetched %d orders for %s", order_count, program.name)

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
    logger.debug("%d packers found for %s", program.packers.count(), program.name)


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
        orders = orders.annotate(total_items=Sum('items__quantity'))

    else:
        orders = orders.annotate(total_items=Sum('id') * 0 + 1)

    # Sort descending to balance assignments
    orders = sorted(orders, key=lambda o: o.total_items, reverse=True)

    # Split orders evenly
    assignment = {packer: [] for packer in packers}
    for idx, order in enumerate(orders):
        packer = packers[idx % len(packers)]
        assignment[packer].append(order)

    logger.debug(
        "Orders assigned to %d packers for %s",
        len(assignment),
        program.name,
    )
    return assignment


def create_child_combined_orders(program: Program, orders: List[Order], packer) -> List[CombinedOrder]:
    """Create child combined orders for a packer."""
    from django.utils import timezone
    
    child_orders = []
    current_year = timezone.now().year
    current_week = timezone.now().isocalendar()[1]
    
    for order in orders:
        # Try to get existing combined order for this program/week
        combined_order, created = CombinedOrder.objects.get_or_create(
            program=program,
            created_at__year=current_year,
            created_at__week=current_week,
            is_parent=False,
            defaults={
                'program': program,
            }
        )
        # Note: packed_by field is currently commented out in model
        # if not created and packer:
        #     combined_order.packed_by = packer
        #     combined_order.save(update_fields=["packed_by"])
        
        combined_order.orders.add(order)
        summarized = combined_order.summarized_items_by_category()
        combined_order.summarized_data = summarized
        combined_order.save(update_fields=["summarized_data"])
        child_orders.append(combined_order)

    logger.debug(
        "Created %d child orders for packer %s in %s",
        len(child_orders), str(packer), program.name
    )
    return child_orders


def create_parent_combined_order(program: Program, child_orders: List[CombinedOrder], packer=None) -> CombinedOrder:
    """Create parent combined order that aggregates all child orders."""
    from django.utils import timezone
    
    now = timezone.now()
    current_year = now.year
    current_week = now.isocalendar()[1]
    
    # Get or create parent combined order for this program/week
    # Use the explicit week/year fields (not created_at lookups)
    parent_order, created = CombinedOrder.objects.get_or_create(
        program=program,
        week=current_week,
        year=current_year,
        is_parent=True,
        defaults={
            'program': program,
            'is_parent': True,
        }
    )
    
    # Note: packed_by field is currently commented out in model
    # if not created and packer:
    #     parent_order.packed_by = packer
    #     parent_order.save(update_fields=["packed_by"])
    
    all_orders = Order.objects.filter(combined_orders__in=child_orders).distinct()
    parent_order.orders.set(all_orders)
    parent_order.summarized_data = parent_order.summarized_items_by_category()
    parent_order.save(update_fields=["summarized_data"])

    logger.debug(
        "Created parent order %s for %s with %d children",
        parent_order.id,
        program.name,
        len(child_orders),
    )
    return parent_order


# ─────────────────────────────
# Split Strategy Validation
# ─────────────────────────────

def validate_split_strategy(program: Program, strategy: str) -> Tuple[bool, List[str]]:
    """
    Validate that a split strategy can be used for a program.
    
    Args:
        program: The program to validate
        strategy: The split strategy to validate
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    packers = list(program.packers.all())
    packer_count = len(packers)
    
    # Validate packer requirements
    if packer_count == 0:
        errors.append(f"Program '{program.name}' has no packers assigned.")
        return False, errors
    
    if strategy == 'none':
        # Single packer strategy - valid for any packer count
        return True, []
    
    if strategy in ('fifty_fifty', 'round_robin'):
        # These require 2+ packers
        if packer_count < 2:
            errors.append(
                f"Strategy '{strategy}' requires at least 2 packers. "
                f"Program '{program.name}' has {packer_count} packer(s)."
            )
            return False, errors
        return True, []
    
    if strategy == 'by_category':
        # Validate that split rules exist and cover all categories
        return validate_by_category_rules(program)
    
    errors.append(f"Unknown split strategy: {strategy}")
    return False, errors


def validate_by_category_rules(program: Program) -> Tuple[bool, List[str]]:
    """
    Validate that BY_CATEGORY split rules are properly configured.
    
    Returns:
        Tuple of (is_valid, error_messages)
    """
    from apps.pantry.models import Category
    
    errors = []
    warnings = []
    
    # Get all split rules for this program
    rules = PackingSplitRule.objects.filter(program=program).prefetch_related('categories', 'subcategories')
    
    if not rules.exists():
        errors.append(
            f"BY_CATEGORY strategy requires PackingSplitRules for program '{program.name}'. "
            "No rules have been defined."
        )
        return False, errors
    
    # Get all categories that have products
    all_categories = set(Category.objects.filter(products__isnull=False).distinct().values_list('id', flat=True))
    
    # Get categories assigned to packers
    assigned_categories = set()
    for rule in rules:
        assigned_categories.update(rule.categories.values_list('id', flat=True))
    
    # Check for unassigned categories
    unassigned = all_categories - assigned_categories
    if unassigned:
        unassigned_names = list(Category.objects.filter(id__in=unassigned).values_list('name', flat=True))
        errors.append(
            f"Categories not assigned to any packer: {', '.join(unassigned_names)}. "
            "All categories with products must be assigned for BY_CATEGORY strategy."
        )
        return False, errors
    
    return True, warnings


def get_program_packers_count(program: Program) -> int:
    """Get the number of packers assigned to a program."""
    return program.packers.count()


# ─────────────────────────────
# Order Splitting Functions
# ─────────────────────────────

def split_orders_by_count(
    orders: List[Order],
    packers: List[Any],
    strategy: str = 'fifty_fifty'
) -> Dict[Any, List[Order]]:
    """
    Split orders among packers by count.
    
    Args:
        orders: List of orders to split
        packers: List of packers to distribute among
        strategy: 'fifty_fifty' or 'round_robin'
        
    Returns:
        Dict mapping each packer to their assigned orders
    """
    if not packers:
        raise ValidationError("No packers provided for splitting")
    
    assignment = {packer: [] for packer in packers}
    
    if strategy == 'fifty_fifty':
        # Split into roughly equal halves
        orders_list = list(orders)
        chunk_size = len(orders_list) // len(packers)
        remainder = len(orders_list) % len(packers)
        
        idx = 0
        for i, packer in enumerate(packers):
            # Give one extra order to first 'remainder' packers
            extra = 1 if i < remainder else 0
            packer_orders = orders_list[idx:idx + chunk_size + extra]
            assignment[packer] = packer_orders
            idx += chunk_size + extra
    
    elif strategy == 'round_robin':
        # Alternate assignment
        orders_list = list(orders)
        for i, order in enumerate(orders_list):
            packer = packers[i % len(packers)]
            assignment[packer].append(order)
    
    return assignment


def split_orders_by_category(
    orders: List[Order],
    packers: List[Any],
    program: Program
) -> Dict[Any, Dict[str, Any]]:
    """
    Split orders by category according to PackingSplitRules.
    
    For BY_CATEGORY strategy, each packer handles specific categories
    across ALL orders (not a subset of orders).
    
    Args:
        orders: List of orders to process
        packers: List of packers
        program: Program with split rules
        
    Returns:
        Dict mapping each packer to their category assignments and item summary
    """
    from apps.pantry.models import Category
    
    # Get split rules for this program
    rules = PackingSplitRule.objects.filter(program=program).prefetch_related('categories', 'subcategories')
    
    # Build packer -> categories mapping
    packer_categories = {}
    for rule in rules:
        category_ids = set(rule.categories.values_list('id', flat=True))
        packer_categories[rule.packer] = category_ids
    
    # Build result structure
    result = {}
    for packer in packers:
        category_ids = packer_categories.get(packer, set())
        result[packer] = {
            'category_ids': category_ids,
            'categories': list(Category.objects.filter(id__in=category_ids)),
            'orders': list(orders),  # All orders, packer filters by category
            'items': defaultdict(lambda: defaultdict(int)),
        }
    
    # Summarize items per packer
    for order in orders:
        for item in order.items.select_related('product__category'):
            product = item.product
            category_id = product.category_id if product.category else None
            
            for packer, data in result.items():
                if category_id in data['category_ids']:
                    category_name = product.category.name if product.category else "Uncategorized"
                    data['items'][category_name][product.name] += item.quantity
    
    # Convert defaultdicts to regular dicts
    for packer in result:
        result[packer]['items'] = dict(result[packer]['items'])
    
    return result


def get_split_preview(
    orders: List[Order],
    program: Program,
    strategy: str
) -> Dict[str, Any]:
    """
    Generate a preview of how orders would be split.
    
    Args:
        orders: Orders to be combined
        program: The program
        strategy: Split strategy to use
        
    Returns:
        Dict with preview data including totals and split assignments
    """
    from apps.pantry.models import Category
    
    packers = list(program.packers.all())
    packer_count = len(packers)
    
    # Calculate total items by category
    category_totals = defaultdict(int)
    product_totals = defaultdict(lambda: defaultdict(int))
    total_items = 0
    total_value = Decimal('0')
    
    for order in orders:
        for item in order.items.select_related('product__category'):
            product = item.product
            category_name = product.category.name if product.category else "Uncategorized"
            category_totals[category_name] += item.quantity
            product_totals[category_name][product.name] += item.quantity
            total_items += item.quantity
            total_value += item.quantity * product.price
    
    preview = {
        'order_count': len(orders),
        'total_items': total_items,
        'total_value': total_value,
        'category_totals': dict(category_totals),
        'product_totals': dict(product_totals),
        'packer_count': packer_count,
        'packers': packers,
        'strategy': strategy,
        'split_preview': [],
    }
    
    if packer_count == 0:
        preview['error'] = "No packers assigned to this program"
        return preview
    
    if packer_count == 1 or strategy == 'none':
        # Single packer gets everything
        preview['split_preview'] = [{
            'packer': packers[0] if packers else None,
            'order_count': len(orders),
            'item_count': total_items,
            'categories': list(category_totals.keys()),
        }]
    elif strategy in ('fifty_fifty', 'round_robin'):
        # Split by order count
        assignment = split_orders_by_count(orders, packers, strategy)
        for packer, packer_orders in assignment.items():
            packer_items = sum(
                item.quantity
                for order in packer_orders
                for item in order.items.all()
            )
            preview['split_preview'].append({
                'packer': packer,
                'order_count': len(packer_orders),
                'item_count': packer_items,
                'categories': 'All categories',
            })
    elif strategy == 'by_category':
        # Split by category
        assignment = split_orders_by_category(orders, packers, program)
        for packer, data in assignment.items():
            packer_items = sum(
                sum(products.values())
                for products in data['items'].values()
            )
            preview['split_preview'].append({
                'packer': packer,
                'order_count': len(orders),  # All orders
                'item_count': packer_items,
                'categories': [c.name for c in data['categories']],
            })
    
    return preview


# ─────────────────────────────
# Combined Order Creation (Admin)
# ─────────────────────────────

def get_eligible_orders(
    program: Program,
    start_date,
    end_date,
    status: str = 'confirmed'
) -> Tuple[List[Order], List[Order], List[str]]:
    """
    Get eligible orders for combining, separating excluded orders.
    
    Args:
        program: The program to filter by
        start_date: Start of date range
        end_date: End of date range
        status: Order status to filter (default: 'confirmed')
        
    Returns:
        Tuple of (eligible_orders, excluded_orders, warning_messages)
    """
    from django.utils import timezone
    
    # Convert dates to datetime if needed
    if hasattr(start_date, 'hour'):
        start_datetime = start_date
    else:
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
    
    if hasattr(end_date, 'hour'):
        end_datetime = end_date
    else:
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )
    
    warnings = []
    
    # Get all orders in the date range for the program
    all_orders = Order.objects.filter(
        account__participant__program=program,
        order_date__gte=start_datetime,
        order_date__lte=end_datetime,
        status=status
    ).select_related('account__participant')
    
    # Separate eligible and excluded orders
    eligible = []
    excluded = []
    
    for order in all_orders:
        if order.is_combined:
            excluded.append(order)
        else:
            eligible.append(order)
    
    if excluded:
        warnings.append(
            f"{len(excluded)} order(s) excluded (already combined)"
        )
    
    return eligible, excluded, warnings


@transaction.atomic
def create_combined_order_with_packing(
    program: Program,
    orders: List[Order],
    strategy: str,
    name: Optional[str] = None
) -> Tuple[CombinedOrder, List[PackingList]]:
    """
    Create a combined order with packing lists based on strategy.
    
    Args:
        program: The program
        orders: Orders to combine
        strategy: Split strategy to use
        name: Optional name for the combined order
        
    Returns:
        Tuple of (combined_order, packing_lists)
        
    Raises:
        ValidationError: If validation fails
    """
    from django.utils import timezone
    
    # Validate strategy
    is_valid, errors = validate_split_strategy(program, strategy)
    if not is_valid:
        raise ValidationError(errors)
    
    # Generate name if not provided
    if not name:
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        name = f"Combined Order - {timestamp}"
    
    # Create the combined order
    now = timezone.now()
    week = now.isocalendar()[1]
    year = now.year
    
    combined_order = CombinedOrder.objects.create(
        name=name,
        program=program,
        split_strategy=strategy,
        week=week,
        year=year,
    )
    
    # Add orders and mark them as combined
    combined_order.orders.add(*orders)
    Order.objects.filter(id__in=[o.id for o in orders]).update(is_combined=True)
    
    # Calculate summarized data
    combined_order.summarized_data = combined_order.summarized_items_by_category()
    combined_order.save(update_fields=['summarized_data'])
    
    # Create packing lists if multiple packers
    packers = list(program.packers.all())
    packing_lists = []
    
    if len(packers) > 1 and strategy != 'none':
        if strategy in ('fifty_fifty', 'round_robin'):
            # Split by order count
            assignment = split_orders_by_count(orders, packers, strategy)
            for packer, packer_orders in assignment.items():
                packing_list = PackingList.objects.create(
                    combined_order=combined_order,
                    packer=packer,
                )
                packing_list.orders.add(*packer_orders)
                packing_list.summarized_data = packing_list.calculate_summarized_data()
                packing_list.save(update_fields=['summarized_data'])
                packing_lists.append(packing_list)
        
        elif strategy == 'by_category':
            # Split by category
            assignment = split_orders_by_category(orders, packers, program)
            for packer, data in assignment.items():
                packing_list = PackingList.objects.create(
                    combined_order=combined_order,
                    packer=packer,
                )
                packing_list.orders.add(*orders)  # All orders
                packing_list.categories.add(*data['categories'])
                packing_list.summarized_data = dict(data['items'])
                packing_list.save(update_fields=['summarized_data'])
                packing_lists.append(packing_list)
    
    logger.info(
        "Created combined order %s for %s with %d orders and %d packing lists",
        combined_order.id, program.name, len(orders), len(packing_lists)
    )
    
    return combined_order, packing_lists


@transaction.atomic
def uncombine_order(combined_order: CombinedOrder) -> int:
    """
    Uncombine a combined order, clearing is_combined flags and removing packing lists.
    
    Args:
        combined_order: The combined order to uncombine
        
    Returns:
        Number of orders that were uncombined
    """
    # Get all orders in this combined order
    order_ids = list(combined_order.orders.values_list('id', flat=True))
    
    # Delete packing lists
    combined_order.packing_lists.all().delete()
    
    # Clear is_combined flag on orders
    Order.objects.filter(id__in=order_ids).update(is_combined=False)
    
    # Clear the orders from the combined order
    combined_order.orders.clear()
    combined_order.summarized_data = {}
    combined_order.save(update_fields=['summarized_data'])
    
    logger.info(
        "Uncombined order %s, cleared %d orders",
        combined_order.id, len(order_ids)
    )
    
    return len(order_ids)


# ─────────────────────────────
# Modular Program Processing
# ─────────────────────────────

def process_program(program: Program, start_of_week, end_of_week) -> bool:
    """Handle weekly combined order creation for a single program with validations."""
    logger.info("[Task] Processing program: %s (ID: %s)", program.name, program.id)

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

        logger.info("Successfully created combined orders for %s", program.name)
        return True

    except ValidationError as ve:
        # Log validation errors but do not send email alerts
        logger.warning("Validation skipped for program %s: %s", program.name, ve)
        return False

    except Exception as e:
        # Log unexpected errors and notify admins
        logger.exception("Error processing program %s: %s", program.name, e)
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

    logger.info(
        "[Task] Processed %d programs, created orders for %d", processed, created
    )
    return processed, created
