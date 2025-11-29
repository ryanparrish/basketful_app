"""
Tests for ProductLimit enforcement across categories and subcategories.

These tests validate business logic that enforces maximum allowable
quantities for products within categories using the OrderValidation class.
This ensures that:
- Category-level limits are enforced correctly
- Subcategory-level limits are enforced correctly
- All limit scopes work correctly (per_household, per_adult, per_child, per_infant, per_order)
- Orders exceeding limits are invalidated with clear errors
- Orders within limits remain valid
- Products without limits are unaffected by validation
- Edge cases (zero quantity, multiple products, missing household data) are handled correctly

This file verifies that critical order validation rules behave
deterministically under different scenarios.
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


# ============================================================
# Limit Scope Tests
# ============================================================


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


# ============================================================
# Subcategory vs Category Level Enforcement
# ============================================================


@pytest.mark.django_db
def test_subcategory_limit_enforced():
    """Test that limits on subcategories are enforced separately.
    """
    participant = ParticipantFactory(adults=1, children=0)
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
    assert "Limit exceeded for Juice" in str(exc_info.value)  # noqa: B101


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


# ============================================================
# Edge Cases
# ============================================================


@pytest.mark.django_db
def test_zero_infants_with_per_infant_scope():
    """Test that per_infant scope with 0 infants allows nothing."""
    participant = ParticipantFactory(adults=2, children=2, diaper_count=0)
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
    participant = ParticipantFactory(adults=2, children=0)
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
    participant = ParticipantFactory(adults=1, children=0)
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
    participant = ParticipantFactory(adults=1, children=0)
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
    participant = ParticipantFactory(adults=1, children=0)
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
