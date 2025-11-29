"""
These tests verify the calculated properties on the Order and OrderItem models.
"""
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from apps.orders.models import Order, OrderItem
from apps.pantry.models import Category, Product
from apps.account.models import Participant
from apps.orders.models import Order, OrderItem

@pytest.mark.django_db
def test_order_item_total_price(order_with_items_setup):
    """Checks that the `total_price()` method on an OrderItem works correctly."""
    # --- ARRANGE ---
    item1 = order_with_items_setup["item1"] # 3 * $2.50
    item2 = order_with_items_setup["item2"] # 2 * $3.00

    # --- ASSERT ---
    assert item1.total_price() == Decimal("7.50")
    assert item2.total_price() == Decimal("6.00")

@pytest.mark.django_db
def test_order_total_price(order_with_items_setup):
    """Checks that the `total_price` property on an Order correctly sums its items."""
    # --- ARRANGE ---
    order = order_with_items_setup["order"] # $7.50 + $6.00

    # --- ASSERT ---
    assert order.total_price == Decimal("13.50")


def create_order(participant, status="pending"):
    """Create a new Order for the participant."""
    return Order.objects.create(
        account=participant.accountbalance, status=status
    )


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
            ) from e
    else:
        try:
            order.clean()
            raise AssertionError("Expected ValidationError but order validated successfully.")
        except ValidationError as e:
            if error_msg:
                joined = " ".join(e.messages)
                assert error_msg in joined, f"Expected '{error_msg}' in {joined}"


def create_category(name):
    return Category.objects.create(name=name)

def create_product(name, price, category):
    return Product.objects.create(name=name, price=price, category=category)

def create_participant(email):
    return Participant.objects.create(email=email)

def create_voucher(participant, multiplier, base_balance):
    # Assuming Voucher model has these fields
    return participant.voucher_set.create(multiplier=multiplier, base_balance=base_balance)

def make_items(product_quantity_pairs):
    items = []
    for product, quantity in product_quantity_pairs:
        items.append(OrderItem(product=product, quantity=quantity))
    return items
