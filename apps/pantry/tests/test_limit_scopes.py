"""
Tests for ProductLimit scope enforcement.

These tests validate that all limit scopes work correctly:
- per_household: multiplies limit by household size
- per_adult: multiplies limit by number of adults
- per_child: multiplies limit by number of children
- per_infant: multiplies limit by diaper_count
- per_order: applies limit without multiplication
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
def test_per_household_scope():
    """Test that per_household scope multiplies limit by household size."""
    # Create participant with household size of 3 (2 adults + 1 child)
    participant = ParticipantFactory(adults=2, children=1)
    order = OrderFactory(account=participant.accountbalance)
    
    # Create category with limit of 5 per household
    category = CategoryFactory(name="Dairy")
    ProductLimitFactory(
        category=category,
        limit=5,
        limit_scope="per_household"
    )
    product = ProductFactory(category=category, price=Decimal("3.00"))
    
    # household_size() = 2 + 1 = 3, so allowed = 5 * 3 = 15
    items = [OrderItemData(product=product, quantity=15)]
    validator = OrderValidation(order)
    
    # Should not raise (exactly at limit)
    validator.validate_order_items(items, participant, order.account)
    
    # Should raise when exceeding
    items_exceed = [OrderItemData(product=product, quantity=16)]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_exceed, participant, order.account)
    assert "Limit exceeded" in str(exc_info.value)  # noqa: B101


@pytest.mark.django_db
def test_per_adult_scope():
    """Test that per_adult scope multiplies limit by number of adults."""
    # Create participant with 3 adults
    participant = ParticipantFactory(adults=3, children=2)
    order = OrderFactory(account=participant.accountbalance)
    
    # Create category with limit of 4 per adult
    category = CategoryFactory(name="Coffee")
    ProductLimitFactory(
        category=category,
        limit=4,
        limit_scope="per_adult"
    )
    product = ProductFactory(category=category, price=Decimal("8.00"))
    
    # allowed = 4 * 3 = 12
    items = [OrderItemData(product=product, quantity=12)]
    validator = OrderValidation(order)
    
    # Should not raise (exactly at limit)
    validator.validate_order_items(items, participant, order.account)
    
    # Should raise when exceeding
    items_exceed = [OrderItemData(product=product, quantity=13)]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_exceed, participant, order.account)
    assert "Limit exceeded" in str(exc_info.value)  # noqa: B101


@pytest.mark.django_db
def test_per_child_scope():
    """Test that per_child scope multiplies limit by number of children."""
    # Create participant with 2 children
    participant = ParticipantFactory(adults=1, children=2)
    order = OrderFactory(account=participant.accountbalance)
    
    # Create category with limit of 3 per child
    category = CategoryFactory(name="Snacks")
    ProductLimitFactory(
        category=category,
        limit=3,
        limit_scope="per_child"
    )
    product = ProductFactory(category=category, price=Decimal("2.00"))
    
    # allowed = 3 * 2 = 6
    items = [OrderItemData(product=product, quantity=6)]
    validator = OrderValidation(order)
    
    # Should not raise (exactly at limit)
    validator.validate_order_items(items, participant, order.account)
    
    # Should raise when exceeding
    items_exceed = [OrderItemData(product=product, quantity=7)]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_exceed, participant, order.account)
    assert "Limit exceeded" in str(exc_info.value)  # noqa: B101


@pytest.mark.django_db
def test_per_infant_scope():
    """Test that per_infant scope multiplies limit by diaper_count."""
    # Create participant with 2 infants (diaper_count)
    participant = ParticipantFactory(adults=1, children=3, diaper_count=2)
    order = OrderFactory(account=participant.accountbalance)
    
    # Create category with limit of 5 per infant
    category = CategoryFactory(name="Diapers")
    ProductLimitFactory(
        category=category,
        limit=5,
        limit_scope="per_infant"
    )
    product = ProductFactory(category=category, price=Decimal("12.00"))
    
    # allowed = 5 * 2 = 10
    items = [OrderItemData(product=product, quantity=10)]
    validator = OrderValidation(order)
    
    # Should not raise (exactly at limit)
    validator.validate_order_items(items, participant, order.account)
    
    # Should raise when exceeding
    items_exceed = [OrderItemData(product=product, quantity=11)]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_exceed, participant, order.account)
    assert "Limit exceeded" in str(exc_info.value)  # noqa: B101


@pytest.mark.django_db
def test_per_order_scope():
    """Test that per_order scope applies limit without multiplication."""
    # Create participant with any household composition
    participant = ParticipantFactory(adults=4, children=3)
    order = OrderFactory(account=participant.accountbalance)
    
    # Create category with limit of 2 per order (not multiplied)
    category = CategoryFactory(name="Specialty Items")
    ProductLimitFactory(
        category=category,
        limit=2,
        limit_scope="per_order"
    )
    product = ProductFactory(category=category, price=Decimal("15.00"))
    
    # allowed = 2 (not multiplied by household size)
    items = [OrderItemData(product=product, quantity=2)]
    validator = OrderValidation(order)
    
    # Should not raise (exactly at limit)
    validator.validate_order_items(items, participant, order.account)
    
    # Should raise when exceeding
    items_exceed = [OrderItemData(product=product, quantity=3)]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_exceed, participant, order.account)
    assert "Limit exceeded" in str(exc_info.value)  # noqa: B101
