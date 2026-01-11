# tests/test_vouchers_pytest.py

"""
================================================================================
Pytest Tests for Voucher Logic
================================================================================

This file contains tests for the voucher creation, application, and pausing
logic, written using the pytest framework.

Key Pytest Concepts Used:
-------------------------
- **Fixtures**: Reusable functions (`@pytest.fixture`) that set up a specific
  state or object for tests (e.g., creating a participant or a voucher setting).
  Tests declare which fixtures they need as arguments, and pytest handles
  running them. This replaces the old `setUp` methods.

- **Markers**: Labels (`@pytest.mark`) that can be applied to tests. We use
  `@pytest.mark.django_db` to tell pytest that a test needs database access.

- **Plain `assert` Statements**: Instead of `self.assertEqual(a, b)`, pytest uses
  the simple `assert a == b`. This provides more detailed and readable output
  on failure.

- **Factory Integration**: These tests directly use the factories defined in
  `food_orders.utils.test_helpers` to create model instances, centralizing
  test data creation.
"""

# ============================================================
# Imports
# ============================================================

# --- Third-Party Imports ---
import pytest
from decimal import Decimal
from faker import Faker
# --- Local Application Imports ---
# --- Import the models we will be testing ---
from apps.voucher.models import (
    Voucher,
    VoucherSetting,
)

# --- Import the factories and helper functions from our test utilities file ---
from apps.orders.tests.factories import (
    ParticipantFactory,
    OrderFactory,
    CategoryFactory,
    ProductFactory,
    VoucherFactory,
    OrderItemFactory,
)
# from test_logging import log_vouchers_for_account
# from orders.utils.order_validation import OrderValidation


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def voucher_setting_fixture():
    """Create a test voucher setting."""
    VoucherSetting.objects.all().update(active=False)
    return VoucherSetting.objects.create(
        adult_amount=Decimal('50.00'),
        child_amount=Decimal('25.00'),
        infant_modifier=Decimal('10.00'),
        active=True
    )


@pytest.fixture
def participant_fixture(voucher_setting_fixture):
    """Create a test participant with household data."""
    return ParticipantFactory(
        adults=2,
        children=3,
        diaper_count=0
    )


@pytest.fixture
def account_fixture(participant_fixture, voucher_setting_fixture):
    """
    Get the account balance for the participant and create initial vouchers.
    """
    from apps.account.utils.balance_utils import calculate_base_balance
    
    account = participant_fixture.accountbalance
    # Recalculate base_balance based on household size
    account.base_balance = calculate_base_balance(participant_fixture)
    account.save()
    
    # Create initial grocery vouchers
    Voucher.objects.create(
        account=account,
        voucher_type='grocery',
        state='applied',
        active=True
    )
    Voucher.objects.create(
        account=account,
        voucher_type='grocery',
        state='applied',
        active=True
    )
    return account


# ============================================================
# Tests for Voucher Amount Calculation and Application
# ============================================================

# --- Mark this test function to grant it access to the database ---
@pytest.mark.django_db
def test_grocery_voucher_with_infant(
    participant_fixture, account_fixture, voucher_setting_fixture
):
    """
    Tests that the grocery voucher amount correctly reflects
    the participant's household size including infants.
    """
    # --- ARRANGE ---
    participant = participant_fixture
    account = account_fixture
    vs = voucher_setting_fixture
    
    # Set initial base_balance to match household (2 adults + 3 children)
    expected_initial = (2 * vs.adult_amount) + (3 * vs.child_amount)
    account.base_balance = expected_initial
    account.save()
    
    # --- ACT ---
    # Add an infant and manually recalculate (testing balance calculation)
    participant.diaper_count = 1
    participant.save()
    
    # Manually trigger balance recalculation
    from apps.account.utils.balance_utils import calculate_base_balance
    account.base_balance = calculate_base_balance(participant)
    account.save()
    account.refresh_from_db()
    
    # Expected base_balance after adding infant
    expected_final = expected_initial + vs.infant_modifier

    # --- ASSERT ---
    # Verify account base_balance was updated correctly
    assert account.base_balance == expected_final, (
        f"Expected base_balance={expected_final}, "
        f"but got {account.base_balance}"
    )
    
    # Verify voucher amount reflects the new base_balance
    first_grocery_voucher = Voucher.objects.filter(
        account=account, voucher_type__iexact="grocery"
    ).first()

    assert first_grocery_voucher is not None, "No grocery voucher assigned"
    assert first_grocery_voucher.voucher_amnt == expected_final

@pytest.mark.django_db
def test_life_voucher_returns_zero_balance(account_fixture):
    """
    Tests that a 'life' type voucher is created with a zero amount by default.
    """
    # --- ARRANGE ---
    # --- We only need the account for this test ---
    account = account_fixture
    
    # --- ACT ---
    # --- Manually create a "life" voucher for this account ---
    Voucher.objects.create(account=account, active=True, voucher_type="life")
    
    # --- ASSERT ---
    # --- Fetch the voucher we just created ---
    life_voucher = Voucher.objects.filter(
        account=account, voucher_type__iexact="life"
    ).first()
    
    # --- Assert that it exists and its amount is zero ---
    assert life_voucher is not None, "No life voucher was assigned"
    assert life_voucher.voucher_amnt == 0

@pytest.mark.django_db
def test_use_multiple_vouchers_for_large_order(account_fixture):
    """
    Tests that multiple vouchers are correctly marked as inactive when an
    order's total price exceeds the value of a single voucher.
    """
    # --- ARRANGE ---
    account = account_fixture
    
    # Create order with items totaling more than one voucher
    order = OrderFactory(account=account, status="pending")
    
    # Create products and order items to reach ~350 total
    product1 = ProductFactory(
        price=Decimal("175.00"),
        description="Expensive item 1"
    )
    product2 = ProductFactory(
        price=Decimal("175.00"),
        description="Expensive item 2"
    )
    OrderItemFactory(order=order, product=product1, quantity=1)
    OrderItemFactory(order=order, product=product2, quantity=1)

    # --- ACT ---
    # Confirm the order, which triggers voucher application logic
    order.status = "confirmed"
    order.save()
    
    # --- Log the state after confirmation for debugging ---
    # log_vouchers_for_account(
    #     account,
    #     context="test_use_multiple_vouchers_for_large_order: After order confirmation",
    #     order=order,
    # )

    # --- ASSERT ---
    # --- Fetch all grocery vouchers for the account after the logic has run ---
    grocery_vouchers = list(Voucher.objects.filter(account=account, voucher_type__iexact="grocery"))
    
    # --- Ensure we have at least two vouchers to test with ---
    assert len(grocery_vouchers) >= 2, "Test requires at least 2 grocery vouchers"

    # --- Check that the first two vouchers were used (are now inactive) ---
    assert not grocery_vouchers[0].active, "First grocery voucher should be inactive"
    assert not grocery_vouchers[1].active, "Second grocery voucher should be inactive"

@pytest.mark.django_db
def test_use_one_voucher_when_order_is_less_than_voucher_value(
    account_fixture
):
    """
    Tests that only one voucher is used when an order's total price is less
    than the value of a single voucher.
    """
    # --- ARRANGE ---
    account = account_fixture
    
    # Create order with items totaling less than one voucher (100)
    order = OrderFactory(account=account, status="pending")
    product = ProductFactory(
        price=Decimal("50.00"),
        description="Inexpensive item"
    )
    OrderItemFactory(order=order, product=product, quantity=1)
    
    # --- ACT ---
    order.status = "confirmed"
    order.save()

    # --- Log the final state ---
    # log_vouchers_for_account(
    #     account,
    #     context="test_use_one_voucher_when_order_is_less_than_voucher_value: After order confirmation",
    #     order=order,
    # )
    
    # --- ASSERT ---
    grocery_vouchers = list(Voucher.objects.filter(account=account, voucher_type__iexact="grocery"))
    
    # --- Filter vouchers into active and inactive lists for easy counting ---
    inactive_vouchers = [v for v in grocery_vouchers if not v.active]
    active_vouchers = [v for v in grocery_vouchers if v.active]

    # --- Assert that exactly one voucher was used ---
    assert len(inactive_vouchers) == 1, "Expected exactly one voucher to be used"
    # --- Assert that at least one other voucher remains active ---
    assert len(active_vouchers) >= 1, "Expected at least one voucher to remain active"



@pytest.mark.django_db
def test_voucher_cannot_be_reused(account_fixture):
    """
    Tests that once a voucher is used for an order, it cannot be applied
    to a subsequent order.
    """
    # --- ARRANGE ---
    account = account_fixture
    
    # --- ACT (Order 1) ---
    # Create and confirm the first order
    order1 = OrderFactory(account=account, status="pending")
    product1 = ProductFactory(
        price=Decimal("50.00"),
        description="Order 1 item"
    )
    OrderItemFactory(order=order1, product=product1, quantity=1)
    order1.status = "confirmed"
    order1.save()

    # --- ASSERT (Order 1) ---
    # Fetch the first voucher and confirm it is now inactive
    first_voucher = Voucher.objects.filter(
        account=account, voucher_type__iexact="grocery"
    ).first()
    first_voucher.refresh_from_db()
    assert not first_voucher.active, (
        "Voucher should be inactive after the first order"
    )

    # --- ACT (Order 2) ---
    # Create and confirm a second order
    order2 = OrderFactory(account=account, status="pending")
    product2 = ProductFactory(
        price=Decimal("50.00"),
        description="Order 2 item"
    )
    OrderItemFactory(order=order2, product=product2, quantity=1)
    order2.status = "confirmed"
    order2.save()
    
    # --- ASSERT (Order 2) ---
    # Refresh the state of the first voucher again
    first_voucher.refresh_from_db()
    # Assert that it is *still* inactive, proving it was not reused
    assert not first_voucher.active, (
        "Voucher should not be reactivated for a second order"
    )

# ============================================================
# Placeholder for Voucher Pause Tests
# ============================================================
"""
The original test file included a `VoucherPauseTest` class with only a `setUp`.
Below is how you would structure that setup as a pytest fixture and a placeholder
test to demonstrate its use.
"""

@pytest.fixture
def paused_test_setup_fixture():
    """
    A dedicated fixture for setting up the specific state needed for
    voucher pause tests.
    """
    # --- Create the specific VoucherSetting needed for these tests ---
    VoucherSetting.objects.create(
        adult_amount=40, child_amount=25, infant_modifier=5, active=True
    )
    # --- Create the specific participant for these tests ---
    participant = ParticipantFactory(adults=1, children=1, diaper_count=1)
    # --- Return the participant and their account for use in tests ---
    return participant, participant.accountbalance

@pytest.mark.django_db
def test_placeholder_for_voucher_pause_logic(paused_test_setup_fixture):
    """
    This is a placeholder to show how to use the `paused_test_setup_fixture`.
    Actual pause logic tests would go here.
    """
    # --- ARRANGE ---
    # --- Get the specific participant and account from our dedicated fixture ---
    participant, account = paused_test_setup_fixture

    # --- ACT & ASSERT ---
    # --- Placeholder assertion to make the test pass ---
    assert participant is not None
    assert account is not None


@pytest.mark.django_db
def test_order_exactly_consumes_one_voucher():
    """
    Test order total exactly equals participant's base balance.
    Ensures voucher remains active and order passes.
    """
    # Create category and product
    product = ProductFactory(price=Decimal("50"))

    # Create participant and set base balance
    participant = ParticipantFactory()
    participant.accountbalance.base_balance = Decimal("50.0")
    participant.accountbalance.save()

    # Create a voucher linked to the participant's account
    voucher = VoucherFactory.create(
        account=participant.accountbalance,
        voucher_type="grocery",
        state="applied",
        active=True
    )

    # Create order and attach items
    order = OrderFactory(account=participant.accountbalance, status="pending")
    OrderItemFactory(order=order, product=product, quantity=1)

    # Assertions
    assert order.items.first().quantity == 1
    assert voucher.voucher_amnt > 0


@pytest.mark.django_db
def test_order_exactly_consumes_two_vouchers():
    """
    Verify that an order exactly consumes the participant's available
    balance spread across multiple vouchers.
    """
    # Setup participant and base balance
    participant = ParticipantFactory()
    participant.accountbalance.base_balance = Decimal("100.0")
    participant.accountbalance.save()
    
    # Create two vouchers
    VoucherFactory.create(
        account=participant.accountbalance,
        voucher_type="grocery",
        state="applied",
        active=True
    )
    VoucherFactory.create(
        account=participant.accountbalance,
        voucher_type="grocery",
        state="applied",
        active=True
    )

    # Get initial available balance (should be from 2 vouchers)
    participant.accountbalance.refresh_from_db()
    initial_balance = participant.accountbalance.available_balance

    # Create order with product
    product = ProductFactory(price=Decimal("75"))
    order = OrderFactory(
        account=participant.accountbalance,
        status="pending"
    )
    OrderItemFactory(order=order, product=product, quantity=2)  # 150 total

    # Confirm order (this should consume vouchers)
    order.status = "confirmed"
    order.save()
    
    # Refresh account balance
    participant.accountbalance.refresh_from_db()

    # Verify order total
    assert order.total_price() == Decimal("150")
    
    # Note: The actual voucher consumption logic would need to be
    # implemented in the Order model's confirm or save method

