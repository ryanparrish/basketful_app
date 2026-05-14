"""
Tests reproducing Issue #63 — double-week cart balance bug.

The symptom:
  During a "double-order week" (an upcoming ProgramPause gives participants
  a 2× spending multiplier), a participant sees a doubled available balance
  in the UI but gets blocked at checkout with "Food balance exceeded by $29.00".

Two distinct root causes are captured here:

  1. BACKEND (test_cart_blocked_when_voucher_multiplier_not_updated):
     validate-cart uses account.available_balance, which multiplies each
     voucher's base_balance by voucher.multiplier.  If the signal that sets
     multiplier=2 never fired (or hasn't fired yet), the endpoint still sees
     the *single-week* available_balance and correctly raises a balance
     violation — but the user was *expecting* the doubled amount, so the
     rejection feels like a bug.

  2. FRONTEND (TestIsOverBudgetLogicBug):
     useCartValidation.isOverBudget computes
         remainingBudget = max(0, available_balance - cartTotal)
         isOverBudget    = cartTotal > remainingBudget
     This fires at cartTotal > available_balance / 2, not at
     cartTotal > available_balance.  For a $200 balance and $129 cart:
         remainingBudget = 71
         isOverBudget    = 129 > 71 = True  ← false positive
     The sider turns red and shows an "over budget" banner even though the
     participant is well within their budget.  isOverBudget does NOT block
     canCheckout directly, but the confusing UI may lead participants to
     remove items unnecessarily — or believe checkout is impossible when
     it isn't.
"""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.orders.tests.factories import (
    CategoryFactory,
    ParticipantFactory,
    ProductFactory,
    UserFactory,
    VoucherFactory,
    VoucherSettingFactory,
)
from core.models import ProgramSettings

# The URL the participant frontend calls (hyphen form, per DRF router convention).
VALIDATE_CART_URL = '/api/v1/orders/validate-cart/'


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def required_singletons(db):
    """Ensure VoucherSetting and ProgramSettings exist."""
    VoucherSettingFactory.create()
    ProgramSettings.get_settings()


def _make_participant(base_balance: Decimal, num_vouchers: int, multiplier: int):
    """Return (user, participant, account) with the specified voucher setup."""
    user = UserFactory()
    participant = ParticipantFactory(user=user)
    account = participant.accountbalance
    account.base_balance = base_balance
    account.save(update_fields=['base_balance'])

    # Remove any vouchers the signal may have created automatically.
    account.vouchers.all().delete()

    for _ in range(num_vouchers):
        VoucherFactory.create(
            account=account,
            state='applied',
            voucher_type='grocery',
            multiplier=multiplier,
        )
    return user, participant, account


# ---------------------------------------------------------------------------
# Backend: validate-cart endpoint
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@pytest.mark.usefixtures('required_singletons')
class TestValidateCartDoubleWeek:
    """
    Reproduce and document the backend half of Issue #63.

    Scenario: 2 grocery vouchers, base_balance=$50 each.
      - Normal week  (multiplier=1): available = $100
      - Double week  (multiplier=2): available = $200
      Cart total: $129
    """

    def test_cart_blocked_when_voucher_multiplier_not_updated(self):
        """
        BUG REPRODUCTION — replicates the "$29 over" error from Issue #63.

        The ProgramPause signal that sets multiplier=2 on vouchers has not
        fired (race condition, signal failure, or manual staff setup gap).
        Vouchers still carry multiplier=1, so available_balance=$100.
        The participant adds $129 of food.  Backend returns valid=false with
        "Food balance exceeded by $29.00", blocking checkout.
        """
        user, _, account = _make_participant(
            base_balance=Decimal('50.00'),
            num_vouchers=2,
            multiplier=1,  # ← bug condition: NOT doubled
        )
        # Verify starting balance so the test is self-documenting.
        assert account.available_balance == Decimal('100.00'), (
            "Available balance should be $100 with 2 vouchers × $50 × multiplier=1"
        )

        food_category = CategoryFactory(name='Pantry')
        product = ProductFactory(category=food_category, price=Decimal('1.00'))

        client = APIClient()
        client.force_authenticate(user=user)

        # $1 × 129 = $129 cart (exactly $29 over the $100 available)
        payload = {'items': [{'product_id': product.id, 'quantity': 129}]}
        response = client.post(VALIDATE_CART_URL, payload, format='json')

        assert response.status_code == 200
        data = response.json()

        # Checkout is blocked — this is the symptom the participant reported.
        assert data['valid'] is False

        blocking = [v for v in data['violations'] if v['severity'] == 'error']
        assert blocking, "Expected at least one blocking violation"

        messages = [v['message'] for v in blocking]
        assert any('$29.00' in m for m in messages), (
            f"Expected 'Food balance exceeded by $29.00' in violations; got: {messages}"
        )

    def test_cart_passes_when_voucher_multiplier_is_doubled(self):
        """
        CORRECT BEHAVIOUR — voucher multiplier properly set to 2 for double week.

        Same cart ($129), same base balance ($50/voucher × 2 vouchers), but
        multiplier=2 → available_balance=$200.  Backend returns valid=true.
        This is what SHOULD happen during a double-order week.
        """
        user, _, account = _make_participant(
            base_balance=Decimal('50.00'),
            num_vouchers=2,
            multiplier=2,  # ← correctly doubled
        )
        assert account.available_balance == Decimal('200.00'), (
            "Available balance should be $200 with 2 vouchers × $50 × multiplier=2"
        )

        food_category = CategoryFactory(name='Pantry')
        product = ProductFactory(category=food_category, price=Decimal('1.00'))

        client = APIClient()
        client.force_authenticate(user=user)

        payload = {'items': [{'product_id': product.id, 'quantity': 129}]}
        response = client.post(VALIDATE_CART_URL, payload, format='json')

        assert response.status_code == 200
        data = response.json()

        # No blocking violations — checkout should be available.
        assert data['valid'] is True, (
            f"Expected valid=True with $129 cart against $200 doubled balance; "
            f"violations: {data.get('violations')}"
        )
        blocking = [v for v in data['violations'] if v['severity'] == 'error']
        assert not blocking, f"Unexpected blocking violations: {blocking}"

    def test_validate_cart_returns_balances_in_response(self):
        """
        The validate-cart response includes a 'balances' block with the
        available, hygiene, and go_fresh amounts at the time of validation.
        These use the key name 'available' (not 'available_balance') — a
        field-name mismatch with the frontend ValidationResponse type that
        should be addressed separately.
        """
        user, _, account = _make_participant(
            base_balance=Decimal('50.00'),
            num_vouchers=2,
            multiplier=2,
        )

        food_category = CategoryFactory(name='Pantry')
        product = ProductFactory(category=food_category, price=Decimal('10.00'))

        client = APIClient()
        client.force_authenticate(user=user)

        payload = {'items': [{'product_id': product.id, 'quantity': 1}]}
        response = client.post(VALIDATE_CART_URL, payload, format='json')

        assert response.status_code == 200
        data = response.json()
        balances = data.get('balances', {})

        # The key is 'available', NOT 'available_balance'.
        # The frontend ValidationContext reads neither — it calls getBalances()
        # separately — but this mismatch is still a latent type-safety bug.
        assert 'available' in balances, (
            "validate-cart response uses 'available' key; "
            "frontend ValidationResponse type incorrectly declares 'available_balance'"
        )
        assert Decimal(balances['available']) == Decimal('200.00')


# ---------------------------------------------------------------------------
# Frontend logic: pure Python re-implementation of isOverBudget
# ---------------------------------------------------------------------------

class TestIsOverBudgetLogicBug:
    """
    Documents the frontend isOverBudget double-counting bug (Issue #63, part 2).

    This class uses no database — it replays the JavaScript arithmetic in
    Python to pin the exact condition where the false positive fires.

    File: participant-frontend/src/shared/hooks/useCartValidation.ts
    Lines: 57-67 (remainingBudget + isOverBudget memos)
    """

    def test_fires_at_half_balance_not_full_balance(self):
        """
        BUG: isOverBudget fires when cartTotal > available_balance / 2.

        With available_balance=$200 and cartTotal=$129 (well within budget):
          remainingBudget = max(0, 200 - 129) = 71
          isOverBudget    = 129 > 71          = True  ← FALSE POSITIVE

        The sider turns red, ProductsPage shows "Your cart exceeds your
        available budget", yet the participant can (and should) check out.
        """
        available_balance = 200.0
        cart_total = 129.0

        # Current (buggy) logic from useCartValidation.ts
        remaining_budget = max(0.0, available_balance - cart_total)  # 71.0
        is_over_budget = cart_total > remaining_budget  # 129 > 71 = True

        assert is_over_budget is True, (
            "Bug confirmed: isOverBudget incorrectly fires when "
            f"cartTotal={cart_total} > remainingBudget={remaining_budget} "
            f"(available={available_balance})"
        )

    def test_correct_logic_does_not_fire_within_balance(self):
        """
        FIXED BEHAVIOUR: isOverBudget compares cartTotal against
        available_balance directly.

          isOverBudget = cartTotal > available_balance
                       = 129 > 200
                       = False  ← correct
        """
        available_balance = 200.0
        cart_total = 129.0

        # Corrected logic (now live in useCartValidation.ts)
        is_over_budget = cart_total > available_balance  # 129 > 200 = False

        assert is_over_budget is False

    def test_boundary_exactly_at_balance(self):
        """Cart total exactly at available_balance is NOT over budget."""
        available_balance = 200.0
        cart_total = 200.0

        is_over_budget_correct = cart_total > available_balance  # False
        assert is_over_budget_correct is False

    def test_truly_over_budget_fires_on_both(self):
        """When cartTotal > available_balance, both versions agree."""
        available_balance = 100.0
        cart_total = 129.0

        # Correct
        is_over_budget_correct = cart_total > available_balance
        assert is_over_budget_correct is True

        # Buggy (also fires, but for wrong internal reason)
        remaining_budget_buggy = max(0.0, available_balance - cart_total)  # 0.0
        is_over_budget_buggy = cart_total > remaining_budget_buggy
        assert is_over_budget_buggy is True
