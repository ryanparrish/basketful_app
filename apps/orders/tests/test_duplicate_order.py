"""
Duplicate order guard tests.

Covers: BEH-005a, BEH-005b, BEH-005c

Business rule: A participant may only have one pending, confirmed, or packing
order at a time. Placing a second order in any of those three statuses while
one already exists must be rejected with a ValidationError.

A cancelled or completed order does NOT count — the participant must be free
to place a new order after a cancellation or once their order is fulfilled.

BEH-005a changed as part of the Issue #50 investigation ("phantom double
orders"): pending orders used to be exempt from this guard on the theory that
they were transient pre-validation drafts. In production they can sit for an
extended, real-world window before staff confirm them (see CLAUDE.md's Order
Status Lifecycle section), and since a pending order doesn't reduce
available_balance until it's confirmed, two simultaneous pending orders could
each independently pass balance validation against the same unconsumed
funds. Blocking a second pending order closes that gap at its source.
"""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.account.models import AccountBalance
from apps.orders.models import Order
from apps.orders.tests.factories import (
    OrderFactory,
    ParticipantFactory,
    ProductFactory,
    VoucherFactory,
    VoucherSettingFactory,
)
from apps.orders.utils.order_validation import OrderItemData


@pytest.mark.django_db
class TestDuplicateOrderGuard:
    """
    A participant cannot place a second active order while one is already open.
    Covers: BEH-005a, BEH-005b, BEH-005c
    """

    @pytest.fixture(autouse=True)
    def voucher_setting(self):
        """Most factory paths need an active VoucherSetting to resolve balance."""
        return VoucherSettingFactory(active=True)

    # ------------------------------------------------------------------
    # BEH-005a: second PENDING order for same participant → rejected
    # ------------------------------------------------------------------

    def test_second_pending_order_for_same_participant_is_rejected(self):
        # Arrange
        participant = ParticipantFactory()
        account = AccountBalance.objects.get(participant=participant)
        OrderFactory(account=account, status="pending")

        # Act + Assert
        duplicate = OrderFactory.build(account=account, status="pending")
        with pytest.raises(ValidationError, match="already.*active.*order|active order"):
            duplicate.full_clean()

    def test_real_checkout_flow_rejects_second_pending_order(self):
        """
        Same as BEH-005a, but through the actual production code path
        (OrderOrchestration.create_order(), used by the participant
        checkout API) instead of calling full_clean() directly on a built
        instance. This is the gap the Issue #50 investigation flagged:
        every prior test in this file only proved the model-level
        validation logic works in isolation, never that the real
        create-order flow actually triggers it.

        Uses two DIFFERENT carts (different product) for the two attempts —
        matching the actual incident, where the participant's two orders had
        different item counts/totals. Submitting the identical cart twice
        would instead hit the unrelated idempotency/duplicate-submission
        cache (generate_idempotency_key), which only catches resubmission of
        the exact same cart and is not what this guard is for.
        """
        from apps.orders.utils.order_utils import OrderOrchestration

        participant = ParticipantFactory()
        account = AccountBalance.objects.get(participant=participant)
        account.base_balance = Decimal("100.00")
        account.save()
        VoucherFactory(account=account, state='applied', voucher_type='grocery', multiplier=1)
        product_a = ProductFactory(price=Decimal("5.00"), quantity_in_stock=50)
        product_b = ProductFactory(price=Decimal("8.00"), quantity_in_stock=50)

        orchestrator = OrderOrchestration()
        # First order succeeds and is left pending.
        orchestrator.create_order(
            account=account,
            order_items_data=[OrderItemData(product=product_a, quantity=1)],
            user=participant.user,
        )
        assert Order.objects.filter(account=account, status="pending").count() == 1

        # Second, different order, while the first is still pending, must be rejected.
        with pytest.raises(ValidationError, match="already.*active.*order|active order"):
            orchestrator.create_order(
                account=account,
                order_items_data=[OrderItemData(product=product_b, quantity=2)],
                user=participant.user,
            )

        assert Order.objects.filter(account=account, status="pending").count() == 1, (
            "The rejected second order must not leave a stray pending row behind"
        )

    # ------------------------------------------------------------------
    # BEH-005b: second CONFIRMED order while a confirmed order exists → rejected
    # ------------------------------------------------------------------

    def test_second_confirmed_order_while_confirmed_order_exists_is_rejected(self):
        # Arrange
        participant = ParticipantFactory()
        account = AccountBalance.objects.get(participant=participant)
        # Use update() to bypass full_clean so we can set status directly
        existing = OrderFactory(account=account, status="pending")
        Order.objects.filter(pk=existing.pk).update(status="confirmed")

        # Act + Assert — trying to confirm a second order must be rejected
        duplicate = OrderFactory.build(account=account, status="confirmed")
        with pytest.raises(ValidationError, match="already.*active.*order|active order|confirmed order|duplicate"):
            duplicate.full_clean()

    # ------------------------------------------------------------------
    # BEH-005c: cancelled order does NOT block a new order (over-block guard)
    # ------------------------------------------------------------------

    def test_new_order_allowed_after_previous_order_is_cancelled(self):
        # Arrange
        participant = ParticipantFactory()
        account = AccountBalance.objects.get(participant=participant)
        cancelled = OrderFactory(account=account, status="pending")
        Order.objects.filter(pk=cancelled.pk).update(status="cancelled")

        # Act — this must NOT raise
        new_order = OrderFactory.build(account=account, status="pending")
        try:
            new_order.full_clean()
        except ValidationError as e:
            messages = str(e).lower()
            if "duplicate" in messages or "active order" in messages:
                pytest.fail(f"New order was wrongly blocked after cancellation: {e}")
