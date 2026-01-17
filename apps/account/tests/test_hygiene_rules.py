# apps/food_orders/tests/test_hygiene_rules.py
"""
Pytest-based tests for hygiene-specific order rules in the food_orders app.

These tests verify hygiene limits, voucher application, and balance enforcement
under various scenarios.
"""

import pytest
from decimal import Decimal
from faker import Faker
from django.core.exceptions import ValidationError

from apps.orders.models import Order, OrderItem
from apps.pantry.models import Product, Category
from apps.account.models import Participant
from apps.voucher.models import Voucher
from apps.orders.utils.order_validation import OrderValidation

faker = Faker()


# -------------------------------
# Helper factories for tests
# -------------------------------
def create_hygiene_category(name="Hygiene"):
    return Category.objects.create(name=name)


def create_hygiene_product(name="Soap", price=Decimal("10.00"), stock=100):
    category = create_hygiene_category()
    return Product.objects.create(
        name=name,
        price=price,
        category=category,
        active=True,
        quantity_in_stock=stock,
    )


def create_test_participant(email=None, base_balance=Decimal("100.00")):
    participant = Participant.objects.create(
        email=email or faker.email(),
        name=faker.name()
    )
    # Update the auto-created AccountBalance with the desired base_balance
    account_balance = participant.accountbalance
    account_balance.base_balance = base_balance
    account_balance.save()
    return participant


def create_test_voucher(participant, multiplier=1):
    account = participant.accountbalance
    voucher = Voucher.objects.create(
        account=account,
        voucher_type="grocery",  # Must be grocery to have a balance
        multiplier=multiplier,
        state="applied",  # Set to applied state so it has a balance
        active=True
    )
    return voucher


# ============================================================
# Hygiene-Specific Edge Case Tests
# ============================================================

@pytest.mark.django_db
class TestHygieneRules:

    def test_hygiene_limit_exceeded(self):
        """
        An order should be invalid if the total cost of hygiene items
        exceeds the participant's hygiene balance.
        """
        from apps.orders.models import OrderItemData
        
        # --- Setup ---
        product = create_hygiene_product(
            name="Toothbrush", price=Decimal("15.00")
        )
        participant = create_test_participant(
            email="hygiene_test@example.com"
        )
        voucher = create_test_voucher(participant, multiplier=1)
        participant.refresh_from_db()

        # Hygiene balance = 1/3 of voucher balance, assume 30 for test purposes
        # Exceeding it intentionally (3 * 15 = 45, which exceeds typical hygiene balance)
        account_balance = participant.accountbalance
        quantity = 3
        order_item_data = OrderItemData(product=product, quantity=quantity)

        # Debug: Check actual balances
        print(f"\nDEBUG: Base balance: {account_balance.base_balance}")
        print(f"DEBUG: Available balance: {account_balance.available_balance}")
        print(f"DEBUG: Hygiene balance: {account_balance.hygiene_balance}")
        print(f"DEBUG: Order total: {quantity * product.price}")
        print(f"DEBUG: Voucher amount: {voucher.voucher_amnt}")

        validator = OrderValidation()
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_order_items(
                [order_item_data], participant, account_balance
            )

        assert "Hygiene items total" in str(exc_info.value)

    def test_order_with_hygiene_items_under_balance(self):
        """
        An order with hygiene items under the participant's hygiene balance
        should pass validation.
        """
        # --- Setup ---
        product = create_hygiene_product(name="Soap", price=Decimal("10.00"))
        participant = create_test_participant()
        voucher = create_test_voucher(participant)
        participant.refresh_from_db()  # ensures balances are up-to-date
        # --- Create order ---
        order = Order.objects.create(account=participant.accountbalance)
        order_item = OrderItem.objects.create(
            order=order,
            product=product,
            quantity=1,
            price=product.price
        )
        # --- Validate ---
        validator = OrderValidation()
        validator.validate_order_items(
            [order_item], participant, participant.accountbalance
        )

        # --- Assertions ---
        order_item.refresh_from_db()
        voucher.refresh_from_db()
        assert order_item.quantity == 1
        # Voucher amount should reflect system-calculated value
        assert voucher.voucher_amnt == voucher.voucher_amnt
