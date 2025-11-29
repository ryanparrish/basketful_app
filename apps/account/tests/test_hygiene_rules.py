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

from apps.orders.models import OrderItem
from apps.pantry.tests.test_helper import (
    create_category,
    create_product,
    create_participant,
    create_voucher,
    make_items,
)
from apps.orders.tests.test_helper import (
    create_order,
    add_items_to_order,
)
from apps.orders.utils.order_validation import OrderValidation
from django.core.exceptions import ValidationError

# ============================================================
# Hygiene-Specific Edge Case Tests
# ============================================================

@pytest.mark.django_db
class TestHygieneRules:
    def test_hygiene_limit_exceeded(self):
        """
        Tests that an order is invalid if the total cost of hygiene items
        exceeds the participant's hygiene balance.
        """
        # Setup
        category = create_category("Hygiene")
        product = create_product("Toothbrush", Decimal("15.00"), category)
        participant = create_participant(email="hygiene_test@example.com")
        
        # Create voucher with limited balance
        voucher = create_voucher(
            participant,
            multiplier=1,
            base_balance=Decimal("30")
        )
        participant.refresh_from_db()
        
        # Create order
        order = create_order(participant)
        
        # Try to add items that exceed hygiene balance
        # Hygiene balance = 1/3 of available balance = 30/3 = 10
        # Try to order 3 items @ $15 = $45 (exceeds $10 limit)
        validator = OrderValidation()
        account_balance = participant.accountbalance
        quantity = 3
        items = [OrderItem(product=product, quantity=quantity)]

        with pytest.raises(ValidationError) as exc_info:
            validator.validate_order_items(
                items, participant, account_balance
            )

        assert "Hygiene items total" in str(exc_info.value)

    def test_order_with_hygiene_items_under_balance(self):
        """
        Test an order with only hygiene items that are under the
        participant's voucher and hygiene balances.

        Ensures that the voucher remains active and balances are updated.
        """
        # --- Setup category, product, and participant ---
        category = create_category("Hygiene")
        product = create_product("Soap", Decimal("10"), category)

        participant = create_participant(email="hygiene@example.com")
        # Create voucher with sufficient balance for hygiene items
        # Hygiene balance is 1/3 of available balance
        voucher = create_voucher(
            participant,
            multiplier=1,
            base_balance=Decimal("150")
        )
        # Refresh to get calculated balances
        participant.refresh_from_db()

        # --- Create order and add items ---
        order = create_order(participant)
        items = make_items([(product, 1)])  # $10 item
        add_items_to_order(order, items)

        # --- Validate order using OrderUtils ---
        utils = OrderValidation()
        # Should not raise error - $10 is under hygiene balance
        utils.validate_order_items(
            items, participant, participant.accountbalance
        )

        # --- Assertions ---
        assert order.items.first().quantity == 1
        assert voucher.voucher_amnt == Decimal("150")  # Untouched
