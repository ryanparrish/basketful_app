# food_orders/tests/test_order_validation.py

"""
Comprehensive pytest-based test suite for validating order creation, voucher usage,
and hygiene balance logic in the food_orders app.

This module refactors the previous Django TestCase classes into pytest functions
with extremely verbose comments for clarity.
"""

from decimal import Decimal
import pytest
from types import SimpleNamespace
from food_orders.models import Order,OrderItem
from food_orders.order_utils import OrderUtils
from test_helper import create_category,create_product,create_participant,create_voucher,create_order,add_items_to_order,make_items

# -----------------------------
# Order validation tests
# -----------------------------

@pytest.mark.django_db
def test_simple_order_creation_verbose():
    """
    Happy path:
    1. Create a category and product
    2. Create participant and voucher
    3. Create order and add items
    4. Validate order items
    5. Assert order and item quantities are correct
    """
    category = create_category("Canned Goods")
    product = create_product("Beans", Decimal("10"), category)

    participant = create_participant(email="simple@example.com")
    voucher = create_voucher(participant, multiplier=1, base_balance=Decimal("50"))

    order = create_order(participant)
    items = make_items([(product, 3)])
    add_items_to_order(order, items)

    utils = OrderUtils()
    utils.validate_order_items(items, participant, participant.accountbalance)

    # Assertions
    assert Order.objects.count() == 1
    assert OrderItem.objects.count() == 1
    assert order.items.first().quantity == 3

# ============================================================
# Order and OrderItem Model Tests
# ============================================================
"""
These tests verify the calculated properties on the Order and OrderItem models.
"""

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

@pytest.mark.django_db
def test_order_with_multiple_products_verbose():
    """
    Happy path with multiple products in different categories.
    Ensures order items and categories interact correctly.
    """
    cat1 = create_category("Canned Goods")
    cat2 = create_category("Hygiene")

    p1 = create_product("Beans", Decimal("5"), cat1)
    p2 = create_product("Soap", Decimal("15"), cat2)

    participant = create_participant(email="multi@example.com")
    create_voucher(participant, multiplier=2, base_balance=Decimal("50"))

    order = create_order(participant)
    items = make_items([(p1, 2), (p2, 1)])
    add_items_to_order(order, items)

    utils = OrderUtils()
    utils.validate_order_items(items, participant, participant.accountbalance)

    # Assertions
    assert order.items.count() == 2
    assert order.items.first().product.name == "Beans"
    assert order.items.last().product.name == "Soap"

@pytest.mark.django_db
def test_order_with_mixed_categories_under_balances():
    """
    Test order with both hygiene and regular items within balance limits.
    Ensures mixed category logic works.
    """
    cat_canned = create_category("Canned Goods")
    cat_hygiene = create_category("Hygiene")

    p1 = create_product("Beans", Decimal("20"), cat_canned)
    p2 = create_product("Soap", Decimal("30"), cat_hygiene)

    participant = create_participant(email="mixed@example.com")
    participant.accountbalance.base_balance = Decimal("150")
    participant.accountbalance.save()

    voucher = create_voucher(participant, multiplier=1, base_balance=Decimal("150"))

    order = create_order(participant)
    items = make_items([(p1, 2), (p2, 1)])
    add_items_to_order(order, items)

    utils = OrderUtils()
    utils.validate_order_items(items, participant, participant.accountbalance)

    # Assertions
    assert order.items.count() == 2
    assert voucher.voucher_amnt == Decimal("150")



@pytest.mark.django_db
def test_products_without_categories_verbose():
    """
    Test products without a category are skipped gracefully.
    Uses in-memory mock product object.
    """
    product_no_cat = SimpleNamespace(name="Uncategorized Product", price=Decimal("10"), category=None)

    participant = create_participant(name="No Category User")
    create_voucher(participant, multiplier=1, base_balance=Decimal("50"))

    items = [type("OrderItemData", (), {"product": product_no_cat, "quantity": 1})]

    utils = OrderUtils()
    # Should not raise any exception
    utils.validate_order_items(items, participant, participant.accountbalance)
