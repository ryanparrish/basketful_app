"""
Duplicate order guard tests.

Covers: BEH-005a, BEH-005b, BEH-005c

Business rule: A participant may only have one confirmed or packing order at a
time. Pending orders are pre-validation drafts and do not count toward this
limit, so multiple pending orders are allowed. Placing a second *confirmed*
order while a confirmed/packing one already exists must be rejected with a
ValidationError.

A cancelled order does NOT count — the participant must be free to reorder
after a cancellation.
"""
import pytest
from django.core.exceptions import ValidationError

from apps.account.models import AccountBalance
from apps.orders.models import Order
from apps.orders.tests.factories import (
    OrderFactory,
    ParticipantFactory,
    VoucherSettingFactory,
)


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
    # BEH-005a: second PENDING order for same participant → allowed
    # Pending orders are pre-validation drafts; the guard only fires on
    # confirmed/packing orders.
    # ------------------------------------------------------------------

    def test_second_pending_order_for_same_participant_is_allowed(self):
        # Arrange
        participant = ParticipantFactory()
        account = AccountBalance.objects.get(participant=participant)
        OrderFactory(account=account, status="pending")

        # Act — must NOT raise
        duplicate = OrderFactory.build(account=account, status="pending")
        duplicate.full_clean()  # should not raise ValidationError

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
