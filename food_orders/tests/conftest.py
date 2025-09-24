# food_orders/tests/test_hygiene_rules.py
"""
Collection of pytest fixtures and helper setup functions for testing the food_orders app.

These fixtures provide reusable, deterministic setup for:
- Voucher settings and participant creation
- Account balance logging
- Order and product setup for formset validation
- Pre-populated orders with items for price calculations

By centralizing these objects here, individual test functions remain concise
and focused on the behavior being tested. This approach mirrors Django's
`setUp` methods but leverages pytest's more flexible and explicit fixture system.
"""

# ============================================================
# Imports
# ============================================================
import pytest
from decimal import Decimal
from django.contrib.auth.models import User

from food_orders.models import VoucherSetting, Order
from food_orders.tests.factories import (
    ParticipantFactory,
    CategoryFactory,
    ProductFactory,
    OrderFactory,
    OrderItemFactory,
)

# ============================================================
# Voucher and Participant Fixtures
# ============================================================

@pytest.fixture
def voucher_setting_fixture():
    """
    Creates a default, active `VoucherSetting` object in the database.

    This fixture ensures that any participant or order created in a test
    can rely on an active voucher setting for balance calculations.
    """
    return VoucherSetting.objects.create(
        adult_amount=40,
        child_amount=25,
        infant_modifier=5,
        active=True,
    )

@pytest.fixture
def participant_fixture(voucher_setting_fixture):
    """
    Creates a Participant instance using the ParticipantFactory.

    This fixture depends on `voucher_setting_fixture` so that any
    signals triggered during participant creation can correctly access
    active voucher settings.
    """
    participant = ParticipantFactory(adults=2, children=3, email="test@test.com")
    return participant

@pytest.fixture
def account_fixture(participant_fixture):
    """
    Retrieves the AccountBalance associated with a participant.

    It depends on `participant_fixture` to ensure the participant exists first.
    Logs the initial state of vouchers for debugging purposes.
    """
    from test_logging import log_vouchers_for_account  # lazy import
    account = participant_fixture.accountbalance
    log_vouchers_for_account(account, "Initial state from fixtures")
    return account

# ============================================================
# User Fixtures
# ============================================================

@pytest.fixture
def test_user_fixture():
    """
    Creates a standard Django User for use in authentication or email-related tests.
    """
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="password123",
    )

# ============================================================
# Order and Product Fixtures
# ============================================================

@pytest.fixture
def order_formset_setup():
    """
    Sets up categories, products, a participant, and a blank order for testing formset validation logic.

    Returns all created objects in a dictionary for convenient access in tests.
    """
    # --- Categories ---
    hygiene_cat = CategoryFactory(name="Hygiene")
    meat_cat = CategoryFactory(name="Meat")
    veg_cat = CategoryFactory(name="Vegetables")

    # --- Products ---
    hygiene_product = ProductFactory(name="Toothbrush", price=Decimal("5.00"), category=hygiene_cat)
    meat_product = ProductFactory(name="Chicken", price=Decimal("6.00"), category=meat_cat, weight_lbs=2.5)
    veg_product = ProductFactory(name="Carrot", price=Decimal("1.00"), category=veg_cat, weight_lbs=0.2)

    # --- Participant and Order ---
    participant = ParticipantFactory()
    order = OrderFactory(account=participant.accountbalance)

    return {
        "hygiene_product": hygiene_product,
        "meat_product": meat_product,
        "veg_product": veg_product,
        "order": order,
    }

@pytest.fixture
def order_with_items_setup():
    """
    Creates an order already populated with multiple items.

    Useful for testing calculations and methods that operate on order items.
    """
    order = OrderFactory()
    item1 = OrderItemFactory(
        order=order,
        product=ProductFactory(name="Canned Beans", price=Decimal("2.50")),
        quantity=3,
    )
    item2 = OrderItemFactory(
        order=order,
        product=ProductFactory(name="Cereal", price=Decimal("3.00")),
        quantity=2,
    )
    return {"order": order, "item1": item1, "item2": item2}
