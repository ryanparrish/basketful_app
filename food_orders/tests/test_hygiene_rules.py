# food_orders/tests/test_hygiene_rules.py
"""
Pytest-based tests for hygiene-specific order rules in the food_orders app.

These tests verify that hygiene limits, voucher application, and
balance enforcement behave correctly under various edge cases.

Fixtures and helper functions from test_helper.py are used for setup,
while OrderUtils performs the actual validation logic.
"""

import pytest
from decimal import Decimal

from food_orders.models import Order
from food_orders.tests.test_helper import (
    create_category,
    create_product,
    create_participant,
    create_voucher,
    create_order,
    add_items_to_order,
    make_items,
)
from food_orders.order_utils import OrderUtils


# ============================================================
# Hygiene-Specific Edge Case Tests
# ============================================================

@pytest.mark.django_db
class TestHygieneRules:
    """
    Test suite for hygiene-specific edge cases, including:
    - Orders exceeding hygiene balances
    - Partial and full consumption of vouchers
    - Orders under voucher and hygiene balances
    """

    def test_hygiene_limit_exceeded(self, order_formset_setup):
        """
        Tests that the formset is invalid if the total cost of hygiene items
        exceeds the participant's hygiene balance.
        """
        _validate_order_formset(
            order=order_formset_setup["order"],
            product=order_formset_setup["hygiene_product"],
            quantity=3,
            should_be_valid=False,
            error_msg="hygiene total exceeds hygiene balance",
        )

    def test_hygiene_order_consumes_one_voucher(self):
        """
        Creates a hygiene-only order that consumes a single voucher.

        Checks that:
        - The voucher amount decreases correctly after the order.
        - The voucher is deactivated if fully consumed.
        """
        # --- Setup participant, category, product, and voucher ---
        cat_hygiene = create_category("Hygiene")
        participant = create_participant(name="Hygiene User")
        voucher = create_voucher(participant, multiplier=1, base_balance=Decimal("50"))

        # --- Create hygiene product and items ---
        product = create_product("Soap", Decimal("40"), cat_hygiene)
        items = make_items([(product, 1)])  # Total $40

        # --- Create order and add items ---
        order = create_order(participant)
        add_items_to_order(order, items)

        # --- Validate order using OrderUtils ---
        utils = OrderUtils()
        utils.validate_order_items(items, participant, participant.accountbalance)

        # --- Assertions ---
        voucher.refresh_from_db()
        assert voucher.voucher_amnt == Decimal("10")  # 50 - 40
        assert voucher.active is True  # Voucher still has remaining balance

    def test_hygiene_order_consumes_two_vouchers(self):
        """
        Creates a hygiene-only order that requires consuming two vouchers.

        Checks that:
        - The first voucher is fully consumed
        - The second voucher covers the remaining amount
        - Both vouchers are updated correctly in amount and active status
        """
        # --- Setup participant, category, product, and two vouchers ---
        cat_hygiene = create_category("Hygiene")
        participant = create_participant(name="Hygiene User")
        voucher1 = create_voucher(participant, multiplier=1, base_balance=Decimal("50"))
        voucher2 = create_voucher(participant, multiplier=1, base_balance=Decimal("30"))

        # --- Create hygiene product and items ---
        product = create_product("Soap", Decimal("70"), cat_hygiene)
        items = make_items([(product, 1)])  # Total $70

        # --- Create order and add items ---
        order = create_order(participant)
        add_items_to_order(order, items)

        # --- Validate order using OrderUtils ---
        utils = OrderUtils()
        utils.validate_order_items(items, participant, participant.accountbalance)

        # --- Refresh vouchers from DB ---
        voucher1.refresh_from_db()
        voucher2.refresh_from_db()

        # --- Assertions ---
        assert voucher1.voucher_amnt == Decimal("0")  # Fully consumed
        assert voucher1.active is False

        assert voucher2.voucher_amnt == Decimal("10")  # Remaining balance
        assert voucher2.active is True

    def test_order_with_hygiene_items_under_balance(self):
        """
        Test an order with only hygiene items that are under the participant's
        voucher and hygiene balances.

        Ensures that the voucher remains active and balances are updated correctly.
        """
        # --- Setup category, product, and participant ---
        category = create_category("Hygiene")
        product = create_product("Soap", Decimal("30"), category)

        participant = create_participant(email="hygiene@example.com")
        participant.accountbalance.base_balance = Decimal("150")
        participant.accountbalance.save()

        voucher = create_voucher(participant, multiplier=1, base_balance=Decimal("150"))

        # --- Create order and add items ---
        order = create_order(participant)
        items = make_items([(product, 1)])
        add_items_to_order(order, items)

        # --- Validate order using OrderUtils ---
        utils = OrderUtils()
        utils.validate_order_items(items, participant, participant.accountbalance)

        # --- Assertions ---
        assert order.items.first().quantity == 1
        assert voucher.voucher_amnt == Decimal("150")  # Voucher untouched
