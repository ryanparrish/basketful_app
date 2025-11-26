
"""
Collection of helper functions and classes to support pytest-based testing of the food_orders app.

These helpers provide reusable utilities for common testing tasks such as:
- Creating participants, orders, vouchers, and products with sensible defaults
- Building form data for inline formsets
- Logging account balances and voucher states
- Simplifying repetitive test setup steps to keep test functions concise and deterministic

Unlike pytest fixtures (which belong in conftest.py for auto-discovery),
these helpers are plain functions and mixins that can be imported explicitly
into test modules. This separation allows fixtures to manage test state while
helpers focus on logic reuse.
"""

# ============================================================
# Imports
# ============================================================
from decimal import Decimal

from pantry.models import Product, Category, Participant, Voucher
from orders.models import Order, OrderItem
from pantry.tests.factories import (
    CategoryFactory,
    ProductFactory,
    ParticipantFactory,
    VoucherFactory,
)
from django.core.exceptions import ValidationError


# ============================================================
# Standalone Helper Functions
# ============================================================

def make_items(product_quantity_list):
    """
    Converts a list of (product, quantity) tuples into lightweight objects
    mimicking OrderItem instances for testing purposes.

    Args:
        product_quantity_list (list): List of tuples (product_instance, quantity)

    Returns:
        list: List of simple objects with `product` and `quantity` attributes
    """
    return [
        type("OrderItemData", (), {"product": product, "quantity": qty})
        for product, qty in product_quantity_list
    ]

# ============================================================
# Factory Wrappers
# ============================================================

def create_category(name="Category"):
    """Create a Category using the factory."""
    return CategoryFactory(name=name)

def create_product(name, price, category, weight_lbs=0.0, quantity=10):
    """Create a Product using the factory."""
    return ProductFactory(
        name=name,
        price=Decimal(price),
        category=category,
        weight_lbs=weight_lbs,
        quantity_in_stock=quantity,
    )

def create_participant(name="Test User", email="test@example.com", adults=1, children=0, infants=0):
    """
    Create a Participant using the factory with default values and reset balances.
    """
    participant = ParticipantFactory(
        name=name, email=email, adults=adults, children=children, diaper_count=infants
    )

    return participant

def create_voucher(participant, multiplier=1, base_balance=Decimal("0")):
    """
    Create a Voucher linked to a participant's account balance.
    """
    account = participant.accountbalance
    account.base_balance = base_balance
    account.save()
    return VoucherFactory(account=account, multiplier=multiplier)

def create_order(participant, status_type="pending"):
    """Create a new Order for the participant."""
    return Order.objects.create(account=participant.accountbalance, status_type=status_type)

def add_items_to_order(order, items):
    """Add lightweight item objects (from make_items) to the order."""
    for item in items:
        OrderItem.objects.create(order=order, product=item.product, quantity=item.quantity)

def _validate_order_logic(order, should_be_valid=True, error_msg=None):
    """
    Helper to run order.clean() and check business rule enforcement.

    Args:
        order (Order): The order instance to validate.
        should_be_valid (bool): Whether validation should succeed.
        error_msg (str, optional): Expected message fragment if invalid.
    """
    if should_be_valid:
        try:
            order.clean()
        except ValidationError as e:
            raise AssertionError(
                f"Expected order to be valid but got ValidationError: {e.messages}"
            )
    else:
        try:
            order.clean()
            raise AssertionError("Expected ValidationError but order validated successfully.")
        except ValidationError as e:
            if error_msg:
                joined = " ".join(e.messages)
                assert error_msg in joined, f"Expected '{error_msg}' in {joined}"
