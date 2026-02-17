"""
Tests for ProductLimit uniqueness and isolation.

These tests validate that product limits are uniquely enforced based on
their specific configuration, ensuring that:
- Different categories have independent limits
- Different subcategories within the same category have independent limits
- A frozen meat limit doesn't enforce against regular meat
- Each limit is isolated to its specific category/subcategory scope
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
def test_different_categories_have_independent_limits(high_balance_participant):
    """Test that limits on different categories are enforced independently."""
    participant = high_balance_participant
    order = OrderFactory(account=participant.accountbalance)
    
    # Create two separate categories with different limits
    meat_category = CategoryFactory(name="Meat")
    ProductLimitFactory(
        category=meat_category,
        limit=5,
        limit_scope="per_household"
    )
    
    dairy_category = CategoryFactory(name="Dairy")
    ProductLimitFactory(
        category=dairy_category,
        limit=10,
        limit_scope="per_household"
    )
    
    # Create products in each category
    meat_product = ProductFactory(
        category=meat_category,
        name="Ground Beef",
        price=Decimal("8.00")
    )
    dairy_product = ProductFactory(
        category=dairy_category,
        name="Milk",
        price=Decimal("3.00")
    )
    
    validator = OrderValidation(order)
    
    # Should allow 5 meat + 10 dairy (each at their own limit)
    items = [
        OrderItemData(product=meat_product, quantity=5),
        OrderItemData(product=dairy_product, quantity=10),
    ]
    validator.validate_order_items(items, participant, order.account)
    
    # Should fail when meat exceeds its limit (dairy is fine)
    items_meat_exceed = [
        OrderItemData(product=meat_product, quantity=6),
        OrderItemData(product=dairy_product, quantity=10),
    ]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_meat_exceed, participant, order.account)
    assert "Meat" in str(exc_info.value)  # noqa: B101
    assert "Dairy" not in str(exc_info.value)  # noqa: B101
    
    # Should fail when dairy exceeds its limit (meat is fine)
    items_dairy_exceed = [
        OrderItemData(product=meat_product, quantity=5),
        OrderItemData(product=dairy_product, quantity=11),
    ]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_dairy_exceed, participant, order.account)
    assert "Dairy" in str(exc_info.value)  # noqa: B101
    assert "Meat" not in str(exc_info.value)  # noqa: B101


@pytest.mark.django_db
def test_subcategories_have_independent_limits_from_parent_category(high_balance_participant):
    """Test that subcategory limits don't affect parent category limits."""
    participant = high_balance_participant
    order = OrderFactory(account=participant.accountbalance)
    
    # Create meat category with a general limit
    meat_category = CategoryFactory(name="Meat")
    ProductLimitFactory(
        category=meat_category,
        limit=10,
        limit_scope="per_household"
    )
    
    # Create frozen meat subcategory with its own limit
    frozen_meat_subcat = SubcategoryFactory(
        name="Frozen Meat",
        category=meat_category
    )
    ProductLimitFactory(
        category=meat_category,
        subcategory=frozen_meat_subcat,
        limit=3,
        limit_scope="per_household"
    )
    
    # Create products
    regular_meat = ProductFactory(
        category=meat_category,
        subcategory=None,  # No subcategory
        name="Fresh Chicken",
        price=Decimal("6.00")
    )
    frozen_meat = ProductFactory(
        category=meat_category,
        subcategory=frozen_meat_subcat,
        name="Frozen Beef",
        price=Decimal("5.00")
    )
    
    validator = OrderValidation(order)
    
    # Should allow 10 regular meat + 3 frozen meat (independent limits)
    items = [
        OrderItemData(product=regular_meat, quantity=10),
        OrderItemData(product=frozen_meat, quantity=3),
    ]
    validator.validate_order_items(items, participant, order.account)
    
    # Frozen meat limit should not affect regular meat
    items_exceed_frozen = [
        OrderItemData(product=regular_meat, quantity=10),
        OrderItemData(product=frozen_meat, quantity=4),
    ]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_exceed_frozen, participant, order.account)
    assert "Frozen Meat" in str(exc_info.value)  # noqa: B101
    assert "Fresh Chicken" not in str(exc_info.value)  # noqa: B101


@pytest.mark.django_db
def test_multiple_subcategories_each_have_unique_limits():
    """Test that multiple subcategories within same category have independent limits."""
    participant = ParticipantFactory(adults=1, children=0)
    order = OrderFactory(account=participant.accountbalance)
    
    # Create beverage category with multiple subcategories
    beverage_category = CategoryFactory(name="Beverages")
    
    # Create subcategories with different limits
    juice_subcat = SubcategoryFactory(name="Juice", category=beverage_category)
    ProductLimitFactory(
        category=beverage_category,
        subcategory=juice_subcat,
        limit=4,
        limit_scope="per_household"
    )
    
    soda_subcat = SubcategoryFactory(name="Soda", category=beverage_category)
    ProductLimitFactory(
        category=beverage_category,
        subcategory=soda_subcat,
        limit=6,
        limit_scope="per_household"
    )
    
    milk_subcat = SubcategoryFactory(name="Milk", category=beverage_category)
    ProductLimitFactory(
        category=beverage_category,
        subcategory=milk_subcat,
        limit=2,
        limit_scope="per_household"
    )
    
    # Create products
    juice = ProductFactory(
        category=beverage_category,
        subcategory=juice_subcat,
        name="Orange Juice",
        price=Decimal("4.00")
    )
    soda = ProductFactory(
        category=beverage_category,
        subcategory=soda_subcat,
        name="Cola",
        price=Decimal("2.00")
    )
    milk = ProductFactory(
        category=beverage_category,
        subcategory=milk_subcat,
        name="Whole Milk",
        price=Decimal("3.50")
    )
    
    validator = OrderValidation(order)
    
    # Should allow 4 juice + 6 soda + 2 milk (each at their own limit)
    items = [
        OrderItemData(product=juice, quantity=4),
        OrderItemData(product=soda, quantity=6),
        OrderItemData(product=milk, quantity=2),
    ]
    validator.validate_order_items(items, participant, order.account)
    
    # Exceeding juice limit shouldn't affect soda or milk
    items_exceed_juice = [
        OrderItemData(product=juice, quantity=5),
        OrderItemData(product=soda, quantity=6),
        OrderItemData(product=milk, quantity=2),
    ]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_exceed_juice, participant, order.account)
    assert "Juice" in str(exc_info.value)  # noqa: B101
    assert "Soda" not in str(exc_info.value)  # noqa: B101
    assert "Milk" not in str(exc_info.value)  # noqa: B101
    
    # Exceeding soda limit shouldn't affect juice or milk
    items_exceed_soda = [
        OrderItemData(product=juice, quantity=4),
        OrderItemData(product=soda, quantity=7),
        OrderItemData(product=milk, quantity=2),
    ]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_exceed_soda, participant, order.account)
    assert "Soda" in str(exc_info.value)  # noqa: B101
    assert "Juice" not in str(exc_info.value)  # noqa: B101
    assert "Milk" not in str(exc_info.value)  # noqa: B101


@pytest.mark.django_db
def test_frozen_meat_limit_does_not_enforce_regular_meat_limit():
    """Test that a frozen meat limit is completely independent from regular meat."""
    participant = ParticipantFactory(adults=2, children=1, high_balance=True)  # household of 3
    order = OrderFactory(account=participant.accountbalance)
    
    # Create meat category
    meat_category = CategoryFactory(name="Meat")
    
    # Create frozen meat subcategory with strict limit
    frozen_subcat = SubcategoryFactory(name="Frozen Meat", category=meat_category)
    ProductLimitFactory(
        category=meat_category,
        subcategory=frozen_subcat,
        limit=2,  # 2 per household = 6 for household of 3
        limit_scope="per_household"
    )
    
    # Regular meat has no limit
    fresh_subcat = SubcategoryFactory(name="Fresh Meat", category=meat_category)
    # No ProductLimit for fresh meat
    
    # Create products
    frozen_beef = ProductFactory(
        category=meat_category,
        subcategory=frozen_subcat,
        name="Frozen Ground Beef",
        price=Decimal("5.00")
    )
    fresh_chicken = ProductFactory(
        category=meat_category,
        subcategory=fresh_subcat,
        name="Fresh Chicken Breast",
        price=Decimal("7.00")
    )
    
    validator = OrderValidation(order)
    
    # Should allow unlimited fresh meat even with frozen meat at limit
    items = [
        OrderItemData(product=frozen_beef, quantity=6),  # At limit (2 * 3)
        OrderItemData(product=fresh_chicken, quantity=100),  # No limit
    ]
    validator.validate_order_items(items, participant, order.account)
    
    # Should only fail on frozen meat, not fresh
    items_exceed_frozen = [
        OrderItemData(product=frozen_beef, quantity=7),  # Exceeds limit
        OrderItemData(product=fresh_chicken, quantity=100),  # Still OK
    ]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_exceed_frozen, participant, order.account)
    assert "Frozen Meat" in str(exc_info.value)  # noqa: B101
    assert "Fresh" not in str(exc_info.value)  # noqa: B101


@pytest.mark.django_db
def test_same_limit_value_different_categories_enforced_separately():
    """Test that categories with the same limit value are still enforced separately."""
    participant = ParticipantFactory(adults=1, children=0)
    order = OrderFactory(account=participant.accountbalance)
    
    # Create three categories all with limit of 5
    cat1 = CategoryFactory(name="Category A")
    ProductLimitFactory(
        category=cat1,
        limit=5,
        limit_scope="per_household"
    )
    
    cat2 = CategoryFactory(name="Category B")
    ProductLimitFactory(
        category=cat2,
        limit=5,
        limit_scope="per_household"
    )
    
    cat3 = CategoryFactory(name="Category C")
    ProductLimitFactory(
        category=cat3,
        limit=5,
        limit_scope="per_household"
    )
    
    # Create products
    prod_a = ProductFactory(category=cat1, name="Product A", price=Decimal("1.00"))
    prod_b = ProductFactory(category=cat2, name="Product B", price=Decimal("1.00"))
    prod_c = ProductFactory(category=cat3, name="Product C", price=Decimal("1.00"))
    
    validator = OrderValidation(order)
    
    # Should allow 5 from each category (15 total)
    items = [
        OrderItemData(product=prod_a, quantity=5),
        OrderItemData(product=prod_b, quantity=5),
        OrderItemData(product=prod_c, quantity=5),
    ]
    validator.validate_order_items(items, participant, order.account)
    
    # Exceeding one shouldn't affect others
    items_exceed_a = [
        OrderItemData(product=prod_a, quantity=6),
        OrderItemData(product=prod_b, quantity=5),
        OrderItemData(product=prod_c, quantity=5),
    ]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_exceed_a, participant, order.account)
    assert "Category A" in str(exc_info.value)  # noqa: B101
    assert "Category B" not in str(exc_info.value)  # noqa: B101
    assert "Category C" not in str(exc_info.value)  # noqa: B101


@pytest.mark.django_db
def test_different_scopes_on_same_category_are_independent():
    """Test that limits with different scopes on same category work independently."""
    # Create participant with 2 adults, 1 child
    participant = ParticipantFactory(adults=2, children=1)
    order = OrderFactory(account=participant.accountbalance)
    
    # Create category with subcategories that have different scopes
    snack_category = CategoryFactory(name="Snacks")
    
    # Adult snacks: per_adult scope
    adult_snacks = SubcategoryFactory(name="Adult Snacks", category=snack_category)
    ProductLimitFactory(
        category=snack_category,
        subcategory=adult_snacks,
        limit=3,
        limit_scope="per_adult"  # 3 * 2 = 6
    )
    
    # Kid snacks: per_child scope
    kid_snacks = SubcategoryFactory(name="Kid Snacks", category=snack_category)
    ProductLimitFactory(
        category=snack_category,
        subcategory=kid_snacks,
        limit=5,
        limit_scope="per_child"  # 5 * 1 = 5
    )
    
    # Create products
    adult_product = ProductFactory(
        category=snack_category,
        subcategory=adult_snacks,
        name="Coffee",
        price=Decimal("8.00")
    )
    kid_product = ProductFactory(
        category=snack_category,
        subcategory=kid_snacks,
        name="Fruit Snacks",
        price=Decimal("2.00")
    )
    
    validator = OrderValidation(order)
    
    # Should allow 6 adult snacks (per_adult) + 5 kid snacks (per_child)
    items = [
        OrderItemData(product=adult_product, quantity=6),
        OrderItemData(product=kid_product, quantity=5),
    ]
    validator.validate_order_items(items, participant, order.account)
    
    # Exceeding adult limit shouldn't affect kid limit
    items_exceed_adult = [
        OrderItemData(product=adult_product, quantity=7),
        OrderItemData(product=kid_product, quantity=5),
    ]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_exceed_adult, participant, order.account)
    assert "Adult Snacks" in str(exc_info.value)  # noqa: B101
    assert "Kid Snacks" not in str(exc_info.value)  # noqa: B101


@pytest.mark.django_db
def test_per_adult_scope_unique_to_category():
    """Test that per_adult scope is calculated independently per category."""
    participant = ParticipantFactory(adults=3, children=0)
    order = OrderFactory(account=participant.accountbalance)
    
    # Category A: per_adult with limit 2 (3 adults = 6 allowed)
    cat_a = CategoryFactory(name="Coffee")
    ProductLimitFactory(
        category=cat_a,
        limit=2,
        limit_scope="per_adult"
    )
    
    # Category B: per_adult with limit 4 (3 adults = 12 allowed)
    cat_b = CategoryFactory(name="Energy Drinks")
    ProductLimitFactory(
        category=cat_b,
        limit=4,
        limit_scope="per_adult"
    )
    
    prod_a = ProductFactory(category=cat_a, name="Coffee", price=Decimal("5.00"))
    prod_b = ProductFactory(category=cat_b, name="Energy Drink", price=Decimal("3.00"))
    
    validator = OrderValidation(order)
    
    # Each category calculates per_adult independently
    items = [
        OrderItemData(product=prod_a, quantity=6),   # 2 * 3 adults = 6
        OrderItemData(product=prod_b, quantity=12),  # 4 * 3 adults = 12
    ]
    validator.validate_order_items(items, participant, order.account)
    
    # Exceeding coffee limit doesn't affect energy drinks
    items_exceed_a = [
        OrderItemData(product=prod_a, quantity=7),
        OrderItemData(product=prod_b, quantity=12),
    ]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_exceed_a, participant, order.account)
    assert "Coffee" in str(exc_info.value)  # noqa: B101
    assert "Energy Drink" not in str(exc_info.value)  # noqa: B101


@pytest.mark.django_db
def test_per_child_scope_unique_to_subcategory():
    """Test that per_child scope is calculated independently per subcategory."""
    participant = ParticipantFactory(adults=1, children=4, high_balance=True)
    order = OrderFactory(account=participant.accountbalance)
    
    # Parent category
    kid_items = CategoryFactory(name="Kids Items")
    
    # Subcategory A: per_child with limit 2 (4 children = 8 allowed)
    toys = SubcategoryFactory(name="Toys", category=kid_items)
    ProductLimitFactory(
        category=kid_items,
        subcategory=toys,
        limit=2,
        limit_scope="per_child"
    )
    
    # Subcategory B: per_child with limit 3 (4 children = 12 allowed)
    books = SubcategoryFactory(name="Books", category=kid_items)
    ProductLimitFactory(
        category=kid_items,
        subcategory=books,
        limit=3,
        limit_scope="per_child"
    )
    
    toy_product = ProductFactory(
        category=kid_items,
        subcategory=toys,
        name="Action Figure",
        price=Decimal("10.00")
    )
    book_product = ProductFactory(
        category=kid_items,
        subcategory=books,
        name="Picture Book",
        price=Decimal("8.00")
    )
    
    validator = OrderValidation(order)
    
    # Each subcategory calculates per_child independently
    items = [
        OrderItemData(product=toy_product, quantity=8),   # 2 * 4 children = 8
        OrderItemData(product=book_product, quantity=12),  # 3 * 4 children = 12
    ]
    validator.validate_order_items(items, participant, order.account)
    
    # Exceeding toys limit doesn't affect books
    items_exceed_toys = [
        OrderItemData(product=toy_product, quantity=9),
        OrderItemData(product=book_product, quantity=12),
    ]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_exceed_toys, participant, order.account)
    assert "Toys" in str(exc_info.value)  # noqa: B101
    assert "Books" not in str(exc_info.value)  # noqa: B101


@pytest.mark.django_db
def test_per_infant_scope_unique_to_subcategory():
    """Test that per_infant scope is calculated independently per subcategory."""
    participant = ParticipantFactory(adults=1, children=2, diaper_count=2, high_balance=True)
    order = OrderFactory(account=participant.accountbalance)
    
    # Parent category
    baby_items = CategoryFactory(name="Baby Items")
    
    # Subcategory A: per_infant with limit 5 (2 infants = 10 allowed)
    diapers = SubcategoryFactory(name="Diapers", category=baby_items)
    ProductLimitFactory(
        category=baby_items,
        subcategory=diapers,
        limit=5,
        limit_scope="per_infant"
    )
    
    # Subcategory B: per_infant with limit 3 (2 infants = 6 allowed)
    wipes = SubcategoryFactory(name="Wipes", category=baby_items)
    ProductLimitFactory(
        category=baby_items,
        subcategory=wipes,
        limit=3,
        limit_scope="per_infant"
    )
    
    diaper_product = ProductFactory(
        category=baby_items,
        subcategory=diapers,
        name="Diapers",
        price=Decimal("15.00")
    )
    wipes_product = ProductFactory(
        category=baby_items,
        subcategory=wipes,
        name="Baby Wipes",
        price=Decimal("5.00")
    )
    
    validator = OrderValidation(order)
    
    # Each subcategory calculates per_infant independently
    items = [
        OrderItemData(product=diaper_product, quantity=10),  # 5 * 2 infants = 10
        OrderItemData(product=wipes_product, quantity=6),    # 3 * 2 infants = 6
    ]
    validator.validate_order_items(items, participant, order.account)
    
    # Exceeding wipes limit doesn't affect diapers
    items_exceed_wipes = [
        OrderItemData(product=diaper_product, quantity=10),
        OrderItemData(product=wipes_product, quantity=7),
    ]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_exceed_wipes, participant, order.account)
    assert "Wipes" in str(exc_info.value)  # noqa: B101
    assert "Diapers" not in str(exc_info.value)  # noqa: B101


@pytest.mark.django_db
def test_per_household_scope_unique_to_category():
    """Test that per_household scope is calculated independently per category."""
    participant = ParticipantFactory(adults=2, children=3)  # household of 5
    order = OrderFactory(account=participant.accountbalance)
    
    # Category A: per_household with limit 2 (5 household = 10 allowed)
    cat_a = CategoryFactory(name="Bread")
    ProductLimitFactory(
        category=cat_a,
        limit=2,
        limit_scope="per_household"
    )
    
    # Category B: per_household with limit 1 (5 household = 5 allowed)
    cat_b = CategoryFactory(name="Eggs")
    ProductLimitFactory(
        category=cat_b,
        limit=1,
        limit_scope="per_household"
    )
    
    prod_a = ProductFactory(category=cat_a, name="Whole Wheat Bread", price=Decimal("3.00"))
    prod_b = ProductFactory(category=cat_b, name="Eggs Dozen", price=Decimal("4.00"))
    
    validator = OrderValidation(order)
    
    # Each category calculates per_household independently
    items = [
        OrderItemData(product=prod_a, quantity=10),  # 2 * 5 household = 10
        OrderItemData(product=prod_b, quantity=5),   # 1 * 5 household = 5
    ]
    validator.validate_order_items(items, participant, order.account)
    
    # Exceeding bread limit doesn't affect eggs
    items_exceed_a = [
        OrderItemData(product=prod_a, quantity=11),
        OrderItemData(product=prod_b, quantity=5),
    ]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_exceed_a, participant, order.account)
    assert "Bread" in str(exc_info.value)  # noqa: B101
    assert "Eggs" not in str(exc_info.value)  # noqa: B101


@pytest.mark.django_db
def test_per_order_scope_unique_to_subcategory():
    """Test that per_order scope is applied independently per subcategory."""
    participant = ParticipantFactory(adults=5, children=3)  # Large household
    order = OrderFactory(account=participant.accountbalance)
    
    # Parent category
    specialty = CategoryFactory(name="Specialty Items")
    
    # Subcategory A: per_order with limit 2 (fixed at 2 regardless of household)
    gift_cards = SubcategoryFactory(name="Gift Cards", category=specialty)
    ProductLimitFactory(
        category=specialty,
        subcategory=gift_cards,
        limit=2,
        limit_scope="per_order"
    )
    
    # Subcategory B: per_order with limit 1 (fixed at 1 regardless of household)
    seasonal = SubcategoryFactory(name="Seasonal", category=specialty)
    ProductLimitFactory(
        category=specialty,
        subcategory=seasonal,
        limit=1,
        limit_scope="per_order"
    )
    
    gift_card = ProductFactory(
        category=specialty,
        subcategory=gift_cards,
        name="$25 Gift Card",
        price=Decimal("25.00")
    )
    seasonal_product = ProductFactory(
        category=specialty,
        subcategory=seasonal,
        name="Holiday Item",
        price=Decimal("20.00")
    )
    
    validator = OrderValidation(order)
    
    # Each subcategory has fixed per_order limit (not multiplied by household)
    items = [
        OrderItemData(product=gift_card, quantity=2),         # Fixed at 2
        OrderItemData(product=seasonal_product, quantity=1),  # Fixed at 1
    ]
    validator.validate_order_items(items, participant, order.account)
    
    # Exceeding seasonal limit doesn't affect gift cards
    items_exceed_seasonal = [
        OrderItemData(product=gift_card, quantity=2),
        OrderItemData(product=seasonal_product, quantity=2),
    ]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_exceed_seasonal, participant, order.account)
    assert "Seasonal" in str(exc_info.value)  # noqa: B101
    assert "Gift Card" not in str(exc_info.value)  # noqa: B101


@pytest.mark.django_db
def test_mixed_scopes_across_categories_all_independent():
    """Test that different scopes across multiple categories all work independently."""
    participant = ParticipantFactory(adults=2, children=2, diaper_count=1, high_balance=True)
    order = OrderFactory(account=participant.accountbalance)
    
    # Category with per_adult scope
    coffee_cat = CategoryFactory(name="Coffee")
    ProductLimitFactory(
        category=coffee_cat,
        limit=3,
        limit_scope="per_adult"  # 3 * 2 = 6
    )
    
    # Category with per_child scope
    snacks_cat = CategoryFactory(name="Kid Snacks")
    ProductLimitFactory(
        category=snacks_cat,
        limit=4,
        limit_scope="per_child"  # 4 * 2 = 8
    )
    
    # Category with per_infant scope
    diapers_cat = CategoryFactory(name="Diapers")
    ProductLimitFactory(
        category=diapers_cat,
        limit=5,
        limit_scope="per_infant"  # 5 * 1 = 5
    )
    
    # Category with per_household scope
    bread_cat = CategoryFactory(name="Bread")
    ProductLimitFactory(
        category=bread_cat,
        limit=2,
        limit_scope="per_household"  # 2 * 4 = 8
    )
    
    # Category with per_order scope
    specialty_cat = CategoryFactory(name="Specialty")
    ProductLimitFactory(
        category=specialty_cat,
        limit=1,
        limit_scope="per_order"  # Fixed at 1
    )
    
    # Create products
    coffee = ProductFactory(category=coffee_cat, name="Coffee", price=Decimal("5.00"))
    snack = ProductFactory(category=snacks_cat, name="Cookies", price=Decimal("3.00"))
    diaper = ProductFactory(category=diapers_cat, name="Diapers", price=Decimal("12.00"))
    bread = ProductFactory(category=bread_cat, name="Bread", price=Decimal("2.50"))
    specialty = ProductFactory(category=specialty_cat, name="Gift", price=Decimal("10.00"))
    
    validator = OrderValidation(order)
    
    # All scopes calculate independently based on their category
    items = [
        OrderItemData(product=coffee, quantity=6),     # per_adult: 3 * 2 = 6
        OrderItemData(product=snack, quantity=8),      # per_child: 4 * 2 = 8
        OrderItemData(product=diaper, quantity=5),     # per_infant: 5 * 1 = 5
        OrderItemData(product=bread, quantity=8),      # per_household: 2 * 4 = 8
        OrderItemData(product=specialty, quantity=1),  # per_order: 1
    ]
    validator.validate_order_items(items, participant, order.account)
    
    # Exceeding coffee (per_adult) doesn't affect any others
    items_exceed_coffee = [
        OrderItemData(product=coffee, quantity=7),
        OrderItemData(product=snack, quantity=8),
        OrderItemData(product=diaper, quantity=5),
        OrderItemData(product=bread, quantity=8),
        OrderItemData(product=specialty, quantity=1),
    ]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_exceed_coffee, participant, order.account)
    assert "Coffee" in str(exc_info.value)  # noqa: B101
    assert "Cookies" not in str(exc_info.value)  # noqa: B101
    assert "Diapers" not in str(exc_info.value)  # noqa: B101
    
    # Exceeding specialty (per_order) doesn't affect any others
    items_exceed_specialty = [
        OrderItemData(product=coffee, quantity=6),
        OrderItemData(product=snack, quantity=8),
        OrderItemData(product=diaper, quantity=5),
        OrderItemData(product=bread, quantity=8),
        OrderItemData(product=specialty, quantity=2),
    ]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate_order_items(items_exceed_specialty, participant, order.account)
    assert "Specialty" in str(exc_info.value)  # noqa: B101
    assert "Coffee" not in str(exc_info.value)  # noqa: B101
    assert "Bread" not in str(exc_info.value)  # noqa: B101
