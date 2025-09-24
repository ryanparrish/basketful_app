"""
Tests for meat weight limit rules in the food_orders app.

These tests validate business logic that enforces maximum allowable weight
for meat products within an order. By using `_validate_order_logic` instead
of Django formsets, the suite focuses on core domain rules rather than form
plumbing. This ensures that:
- Orders exceeding the meat weight cap are invalidated with clear errors.
- Orders within the limit remain valid.
- Non-meat products are unaffected by meat weight constraints.
- Edge cases (zero quantity, multiple meat products) are consistently enforced.

This file is intended for product managers and developers to verify that
critical order validation rules behave deterministically under different
scenarios, regardless of how orders are created (form, API, import).
"""

import pytest
from test_helper import _validate_order_logic


@pytest.mark.django_db
def test_meat_weight_limit_exceeded(order_formset_setup):
    """
    Creates an order with too much meat.

    Checks that:
    - Business logic invalidates the order.
    - Error message indicates the weight limit was exceeded.
    """
    order = order_formset_setup["order"]
    order.items.create(product=order_formset_setup["meat_product"], quantity=3)

    _validate_order_logic(order, should_be_valid=False, error_msg="exceeds weight limit")


@pytest.mark.django_db
def test_meat_within_weight_limit(order_formset_setup):
    """
    Creates an order with meat that is under the weight cap.

    Checks that:
    - Order validates successfully.
    - No error message is raised.
    """
    order = order_formset_setup["order"]
    order.items.create(product=order_formset_setup["meat_product"], quantity=1)

    _validate_order_logic(order, should_be_valid=True)


@pytest.mark.django_db
def test_multiple_meat_products_accumulate_weight(order_formset_setup):
    """
    Creates an order with different meat products that together exceed the weight cap.

    Checks that:
    - The combined weight invalidates the order.
    - The error message indicates the weight limit was exceeded.
    """
    order = order_formset_setup["order"]
    order.items.create(product=order_formset_setup["meat_product"], quantity=2)
    order.items.create(product=order_formset_setup["alt_meat_product"], quantity=2)

    _validate_order_logic(order, should_be_valid=False, error_msg="exceeds weight limit")


@pytest.mark.django_db
def test_non_meat_product_not_affected_by_meat_limit(order_formset_setup):
    """
    Creates an order with non-meat products.

    Checks that:
    - The meat weight cap does not affect these items.
    - The order validates regardless of quantity.
    """
    order = order_formset_setup["order"]
    order.items.create(product=order_formset_setup["non_meat_product"], quantity=10)

    _validate_order_logic(order, should_be_valid=True)


@pytest.mark.django_db
def test_zero_quantity_meat_does_not_trigger_limit(order_formset_setup):
    """
    Creates an order with zero-quantity meat.

    Checks that:
    - The order validates since no meat is actually ordered.
    - No error message is raised.
    """
    order = order_formset_setup["order"]
    order.items.create(product=order_formset_setup["meat_product"], quantity=0)

    _validate_order_logic(order, should_be_valid=True)
