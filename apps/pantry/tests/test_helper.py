
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

from apps.pantry.models import Product, Category
from apps.account.models import Participant
from apps.voucher.models import Voucher
from apps.orders.models import Order, OrderItem
from apps.pantry.tests.factories import (
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