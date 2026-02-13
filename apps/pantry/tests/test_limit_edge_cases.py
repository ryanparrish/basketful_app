"""
Tests for edge cases in limit enforcement.

These tests validate proper handling of:
- Zero infants with per_infant scope
- Zero children with per_child scope
- Multiple products in same category aggregation
- Categories without limits (unlimited)
- Mixed limited and unlimited categories
"""

import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from apps.orders.utils.order_validation import (
    OrderValidation,
    OrderItemData
)
from apps.pantry.tests.factories import (
    CategoryFactory,
    ProductFactory,
    ProductLimitFactory,
    ParticipantFactory,
    OrderFactory,
)


@pytest.mark.django_db
def test_zero_infants_with_per_infant_scope():
    """Test that per_infant scope with 0 infants allows nothing."""
    participant = ParticipantFactory(adults=2, children=2, diaper_count=0, high_balance=True)
    order = OrderFactory(account=participant.accountbalance)
    
    category = CategoryFactory(name="Baby Formula")
    ProductLimitFactory(
        category=category,
        limit=5,
        limit_scope="per_infant"
    )
    product = ProductFactory(category=category, price=Decimal("20.00"))
    
    # allowed = 5 * 0 = 0
    validator = OrderValidation(order)
    
    # Should fail with even 1 item
    items = [OrderItemData(product=product, quantity=1)]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items, participant, order.account)
    assert "Limit exceeded" in str(exc_info.value)  # noqa: B101


@pytest.mark.django_db
def test_zero_children_with_per_child_scope():
    """Test that per_child scope with 0 children allows nothing."""
    participant = ParticipantFactory(adults=2, children=0, high_balance=True)
    order = OrderFactory(account=participant.accountbalance)
    
    category = CategoryFactory(name="Kids Cereal")
    ProductLimitFactory(
        category=category,
        limit=4,
        limit_scope="per_child"
    )
    product = ProductFactory(category=category, price=Decimal("5.00"))
    
    # allowed = 4 * 0 = 0
    validator = OrderValidation(order)
    
    # Should fail with even 1 item
    items = [OrderItemData(product=product, quantity=1)]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items, participant, order.account)
    assert "Limit exceeded" in str(exc_info.value)  # noqa: B101


@pytest.mark.django_db
def test_multiple_products_same_category_aggregate():
    """Test that multiple products in same category are aggregated."""
    participant = ParticipantFactory(adults=1, children=0, high_balance=True)
    order = OrderFactory(account=participant.accountbalance)
    
    category = CategoryFactory(name="Protein")
    ProductLimitFactory(
        category=category,
        limit=10,
        limit_scope="per_household"
    )
    
    chicken = ProductFactory(category=category, name="Chicken", price=Decimal("6.00"))
    beef = ProductFactory(category=category, name="Beef", price=Decimal("8.00"))
    fish = ProductFactory(category=category, name="Fish", price=Decimal("7.00"))
    
    validator = OrderValidation(order)
    
    # 3 + 4 + 3 = 10 (exactly at limit)
    items = [
        OrderItemData(product=chicken, quantity=3),
        OrderItemData(product=beef, quantity=4),
        OrderItemData(product=fish, quantity=3),
    ]
    validator.validate_order_items(items, participant, order.account)
    
    # 3 + 4 + 4 = 11 (exceeds limit)
    items_exceed = [
        OrderItemData(product=chicken, quantity=3),
        OrderItemData(product=beef, quantity=4),
        OrderItemData(product=fish, quantity=4),
    ]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_exceed, participant, order.account)
    assert "Limit exceeded" in str(exc_info.value)  # noqa: B101
    # Verify all products are mentioned in error
    assert "Chicken" in str(exc_info.value)  # noqa: B101
    assert "Beef" in str(exc_info.value)  # noqa: B101
    assert "Fish" in str(exc_info.value)  # noqa: B101


@pytest.mark.django_db
def test_no_limit_set_allows_unlimited():
    """Test that categories without ProductLimit allow unlimited quantities."""
    participant = ParticipantFactory(adults=1, children=0, high_balance=True)
    order = OrderFactory(account=participant.accountbalance)
    
    # Category with no ProductLimit
    category = CategoryFactory(name="Unlimited Category")
    product = ProductFactory(category=category, price=Decimal("1.00"))
    
    validator = OrderValidation(order)
    
    # Should allow very large quantities
    items = [OrderItemData(product=product, quantity=999)]
    validator.validate_order_items(items, participant, order.account)


@pytest.mark.django_db
def test_mixed_limited_and_unlimited_products():
    """Test ordering from both limited and unlimited categories."""
    participant = ParticipantFactory(adults=1, children=0, high_balance=True)
    order = OrderFactory(account=participant.accountbalance)
    
    # Limited category
    limited_cat = CategoryFactory(name="Limited")
    ProductLimitFactory(
        category=limited_cat,
        limit=3,
        limit_scope="per_household"
    )
    limited_product = ProductFactory(category=limited_cat, price=Decimal("5.00"))
    
    # Unlimited category
    unlimited_cat = CategoryFactory(name="Unlimited")
    unlimited_product = ProductFactory(category=unlimited_cat, price=Decimal("1.00"))
    
    validator = OrderValidation(order)
    
    # Should allow 3 limited + 100 unlimited
    items = [
        OrderItemData(product=limited_product, quantity=3),
        OrderItemData(product=unlimited_product, quantity=100),
    ]
    validator.validate_order_items(items, participant, order.account)
    
    # Should fail when limited exceeds
    items_exceed = [
        OrderItemData(product=limited_product, quantity=4),
        OrderItemData(product=unlimited_product, quantity=100),
    ]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_exceed, participant, order.account)
    assert "Limit exceeded" in str(exc_info.value)  # noqa: B101
