"""
Tests for subcategory and category-level limit enforcement.

These tests validate that:
- Subcategory limits are enforced separately from category limits
- Category-level limits aggregate all products in the category
- Mixed subcategory/category scenarios work correctly
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
    SubcategoryFactory,
    ProductFactory,
    ProductLimitFactory,
    ParticipantFactory,
    OrderFactory,
)


@pytest.mark.django_db
def test_subcategory_limit_enforced(high_balance_participant):
    """Test that limits on subcategories are enforced separately.
    """
    participant = high_balance_participant
    order = OrderFactory(account=participant.accountbalance)
    
    # Create category with two subcategories
    category = CategoryFactory(name="Beverages")
    subcat_juice = SubcategoryFactory(name="Juice", category=category)
    subcat_soda = SubcategoryFactory(name="Soda", category=category)
    
    # Apply limit to juice subcategory only
    ProductLimitFactory(
        category=category,
        subcategory=subcat_juice,
        limit=3,
        limit_scope="per_household"
    )
    
    juice_product = ProductFactory(
        category=category,
        subcategory=subcat_juice,
        price=Decimal("4.00")
    )
    soda_product = ProductFactory(
        category=category,
        subcategory=subcat_soda,
        price=Decimal("3.00")
    )
    
    # Juice is limited to 3, soda has no limit
    validator = OrderValidation(order)
    
    # Should allow 3 juice + 10 soda
    items = [
        OrderItemData(product=juice_product, quantity=3),
        OrderItemData(product=soda_product, quantity=10),
    ]
    validator.validate_order_items(items, participant, order.account)
    
    # Should fail with 4 juice
    items_exceed = [
        OrderItemData(product=juice_product, quantity=4),
        OrderItemData(product=soda_product, quantity=10),
    ]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(
            items_exceed, participant, order.account
        )
    assert "Subcategory 'Juice'" in str(exc_info.value)  # noqa: B101
    assert "Ordered 4, allowed 3" in str(exc_info.value)  # noqa: B101


@pytest.mark.django_db
def test_category_level_limit_aggregates_all_products():
    """Test that category-level limits aggregate all products in category."""
    participant = ParticipantFactory(adults=1, children=0)
    order = OrderFactory(account=participant.accountbalance)
    
    # Create category with limit
    category = CategoryFactory(name="Canned Goods")
    ProductLimitFactory(
        category=category,
        limit=5,
        limit_scope="per_household"
    )
    
    # Create multiple products in same category
    product1 = ProductFactory(category=category, name="Beans", price=Decimal("2.00"))
    product2 = ProductFactory(category=category, name="Corn", price=Decimal("2.00"))
    product3 = ProductFactory(category=category, name="Soup", price=Decimal("3.00"))
    
    validator = OrderValidation(order)
    
    # Total of 5 products across all items should be at limit
    items = [
        OrderItemData(product=product1, quantity=2),
        OrderItemData(product=product2, quantity=2),
        OrderItemData(product=product3, quantity=1),
    ]
    validator.validate_order_items(items, participant, order.account)
    
    # Total of 6 should exceed
    items_exceed = [
        OrderItemData(product=product1, quantity=2),
        OrderItemData(product=product2, quantity=2),
        OrderItemData(product=product3, quantity=2),
    ]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_exceed, participant, order.account)
    assert "Limit exceeded" in str(exc_info.value)  # noqa: B101
    assert "Canned Goods" in str(exc_info.value)  # noqa: B101
