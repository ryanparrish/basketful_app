"""
Tests for basic category limit enforcement.

These tests validate that category-level limits are enforced correctly
for orders, ensuring that:
- Orders exceeding category limits raise ValidationError
- Orders within limits pass validation
- Products without limits are unaffected
- Zero-quantity items don't trigger validation
"""

import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from apps.orders.utils.order_validation import (
    OrderValidation,
    OrderItemData
)


@pytest.mark.django_db
def test_meat_weight_limit_exceeded(
    order_formset_setup, meat_product_with_manager
):
    """Test that exceeding category limit raises ValidationError."""
    order = order_formset_setup["order"]
    meat_product = meat_product_with_manager["meat_product"]
    participant = order.account.participant

    # Create items that exceed the limit (15 units > 10 limit)
    items = [
        OrderItemData(product=meat_product, quantity=15)
    ]

    validator = OrderValidation(order)

    # Should raise ValidationError since 15 units exceeds limit of 10
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(
            items, participant, order.account
        )

    # B101 assert warning can be ignored in tests
    assert "Limit exceeded" in str(exc_info.value)  # noqa: B101


@pytest.mark.django_db
def test_meat_within_limit(order_formset_setup, meat_product_with_manager):
    """Test that orders within category limit pass validation."""
    order = order_formset_setup["order"]
    meat_product = meat_product_with_manager["meat_product"]
    participant = order.account.participant

    # Create items within the limit (1 unit < 10 limit)
    items = [
        OrderItemData(product=meat_product, quantity=1)
    ]

    validator = OrderValidation(order)

    # Should not raise any exception
    validator.validate_order_items(items, participant, order.account)


@pytest.mark.django_db
def test_non_meat_products_unaffected(order_formset_setup):
    """Test that products without category limits pass validation."""
    order = order_formset_setup["order"]
    veg_product = order_formset_setup["veg_product"]
    participant = order.account.participant

    # Create many non-meat items (should not be limited)
    items = [
        OrderItemData(product=veg_product, quantity=10)
    ]

    validator = OrderValidation(order)

    # Should not raise any exception
    validator.validate_order_items(items, participant, order.account)


@pytest.mark.django_db
def test_zero_quantity_does_not_trigger_validation(
    order_formset_setup, meat_product_with_manager
):
    """Test that zero-quantity items don't trigger validation."""
    order = order_formset_setup["order"]
    meat_product = meat_product_with_manager["meat_product"]
    participant = order.account.participant

    # Create item with zero quantity
    items = [
        OrderItemData(product=meat_product, quantity=0)
    ]

    validator = OrderValidation(order)

    # Should not raise any exception (zero quantity is ignored)
    validator.validate_order_items(items, participant, order.account)
