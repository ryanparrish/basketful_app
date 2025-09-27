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
def test_meat_weight_limit_exceeded(order_formset_setup, meat_product_with_manager):
    order = order_formset_setup["order"]
    meat_product = meat_product_with_manager["meat_product"]

    # This will exceed: 3 × 5.0 = 15.0 > 10 limit
    order.items.create(product=meat_product, quantity=3)

    _validate_order_logic(order, should_be_valid=False, error_msg="exceeds weight limit")

@pytest.mark.django_db
@pytest.mark.parametrize(
    "items, should_be_valid, error_msg",
    [
        (
            # under the cap
            [("meat_product", 1)],
            True,
            None,
        ),
        (
            # meat + alt meat exceed cap
            [("meat_product", 2), ("alt_meat_product", 2)],
            False,
            "exceeds weight limit",
        ),
        (
            # only non-meat, unaffected
            [("non_meat_product", 10)],
            True,
            None,
        ),
        (
            # zero-quantity meat, should not trigger
            [("meat_product", 0)],
            True,
            None,
        ),
    ],
)
def test_meat_weight_rules(order_formset_setup, items, should_be_valid, error_msg):
    """
    Parametrized test covering multiple meat-weight scenarios:

    - Meat within the limit
    - Multiple meats that together exceed the limit
    - Non-meat products unaffected by meat cap
    - Zero-quantity meat not triggering validation
    """
    order = order_formset_setup["order"]

    # Create items for this scenario
    for product_key, qty in items:
        order.items.create(product=order_formset_setup[product_key], quantity=qty)

    # Validate according to expectation
    _validate_order_logic(order, should_be_valid=should_be_valid, error_msg=error_msg)
