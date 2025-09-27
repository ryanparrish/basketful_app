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

from food_orders.models import OrderItem
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
from django.core.exceptions import ValidationError

# ============================================================
# Hygiene-Specific Edge Case Tests
# ============================================================

@pytest.mark.django_db
class TestHygieneRules:
    def test_hygiene_limit_exceeded(self, order_formset_setup):
        """
        Tests that an order is invalid if the total cost of hygiene items
        exceeds the participant's hygiene balance.
        """
        validator = OrderUtils()
        order = order_formset_setup["order"]
        account_balance = order.account  # account_balance is the ForeignKey target
        participant = account_balance.participant  # get participant via account

        product = order_formset_setup["hygiene_product"]
        quantity = 3

        items = [OrderItem(product=product, quantity=quantity)]

        with pytest.raises(ValidationError) as exc_info:
            validator.validate_order_items(items, participant, account_balance)

        assert "Hygiene items total" in str(exc_info.value)

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
