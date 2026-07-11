"""
Program pause blocks ordering during the off week (Issue #78).

Business rules verified:
  1. While a ProgramPause is in progress, the order window reports
     'paused' and can_place_order() is False for every program.
  2. Order creation (the real OrderOrchestration.create_order path used
     by the participant checkout) is rejected server-side during a pause.
  3. validate-cart returns a blocking 'window' violation during a pause.
  4. The pre-pause double-order week (pause 10-14 days out) does NOT
     block ordering — only the pause week itself does.
  5. Archived and past pauses do not block.
  6. A force-open ProgramWindowOverride is the staff escape hatch: it
     keeps the window open and lets orders through even mid-pause.

The in-progress pause predicate is the raw date range
(pause_start <= now <= pause_end) — deliberately NOT
ProgramPause.is_active_gate/multiplier, which match the pre-pause
double-order week and are falsy during the pause proper.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.account.models import AccountBalance
from apps.lifeskills.models import ProgramPause
from apps.orders.models import Order
from apps.orders.tests.factories import (
    ParticipantFactory,
    ProductFactory,
    VoucherFactory,
    VoucherSettingFactory,
)
from apps.orders.utils.order_utils import OrderOrchestration
from apps.orders.utils.order_validation import OrderItemData, OrderValidation
from core.models import ProgramWindowOverride
from core.utils import can_place_order, get_program_window_status

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def voucher_setting():
    return VoucherSettingFactory(active=True)


@pytest.fixture
def participant():
    return ParticipantFactory()


def create_in_progress_pause(**overrides):
    """A pause whose off-week is happening right now.

    Uses objects.create() deliberately — clean() forbids creating pauses
    that start <10 days out, but a real in-progress pause was created in
    the past and is exactly the state Issue #78 is about.
    """
    now = timezone.now()
    defaults = dict(
        pause_start=now - timedelta(days=2),
        pause_end=now + timedelta(days=5),
        reason='Summer break',
    )
    defaults.update(overrides)
    return ProgramPause.objects.create(**defaults)


def fund_account(participant, amount=Decimal('100.00')):
    account = AccountBalance.objects.get(participant=participant)
    account.base_balance = amount
    account.save()
    VoucherFactory(
        account=account, state='applied', voucher_type='grocery', multiplier=1
    )
    return account


# ---------------------------------------------------------------------------
# Window status / can_place_order
# ---------------------------------------------------------------------------

class TestWindowStatusDuringPause:

    def test_window_status_is_paused_during_pause(self, participant):
        pause = create_in_progress_pause()
        ws = get_program_window_status(participant.program)
        assert ws['window_status'] == 'paused'
        expected_seconds = int((pause.pause_end - timezone.now()).total_seconds())
        assert abs(ws['seconds_until_change'] - expected_seconds) <= 5

    def test_can_place_order_false_during_pause(self, participant):
        pause = create_in_progress_pause()
        can_order, context = can_place_order(participant)
        assert can_order is False
        assert context['reason'] == 'Program pause in progress'
        assert context['pause_ends_at'] == pause.pause_end

    def test_pre_pause_double_week_does_not_block(self, participant):
        """A pause 10-14 days out doubles limits but must NOT close windows."""
        now = timezone.now()
        ProgramPause.objects.create(
            pause_start=now + timedelta(days=12),
            pause_end=now + timedelta(days=19),
            reason='Upcoming break',
        )
        ws = get_program_window_status(participant.program)
        assert ws['window_status'] in ('open', 'closed')  # schedule-driven

    def test_archived_pause_does_not_block(self, participant):
        create_in_progress_pause(archived=True, archived_at=timezone.now())
        ws = get_program_window_status(participant.program)
        assert ws['window_status'] != 'paused'

    def test_past_pause_does_not_block(self, participant):
        now = timezone.now()
        ProgramPause.objects.create(
            pause_start=now - timedelta(days=14),
            pause_end=now - timedelta(days=7),
            reason='Last month',
        )
        ws = get_program_window_status(participant.program)
        assert ws['window_status'] != 'paused'

    def test_force_open_override_beats_pause(self, participant):
        create_in_progress_pause()
        ProgramWindowOverride.objects.create(
            program=participant.program,
            force_status='open',
            expires_at=timezone.now() + timedelta(hours=4),
            reason='Staff exception during pause',
        )
        ws = get_program_window_status(participant.program)
        assert ws['window_status'] == 'force_open'
        can_order, _ = can_place_order(participant)
        assert can_order is True


# ---------------------------------------------------------------------------
# Server-side order creation block
# ---------------------------------------------------------------------------

class TestOrderCreationDuringPause:

    def test_create_order_rejected_during_pause(self, participant):
        create_in_progress_pause()
        account = fund_account(participant)
        product = ProductFactory(price=Decimal('5.00'), quantity_in_stock=50)

        with pytest.raises(ValidationError, match='program pause'):
            OrderOrchestration().create_order(
                account=account,
                order_items_data=[OrderItemData(product=product, quantity=1)],
                user=participant.user,
            )
        assert not Order.objects.filter(account=account).exists()

    def test_create_order_succeeds_without_pause(self, participant):
        account = fund_account(participant)
        product = ProductFactory(price=Decimal('5.00'), quantity_in_stock=50)

        OrderOrchestration().create_order(
            account=account,
            order_items_data=[OrderItemData(product=product, quantity=1)],
            user=participant.user,
        )
        assert Order.objects.filter(account=account, status='pending').count() == 1

    def test_force_open_override_lets_order_through_during_pause(self, participant):
        create_in_progress_pause()
        ProgramWindowOverride.objects.create(
            program=participant.program,
            force_status='open',
            expires_at=timezone.now() + timedelta(hours=4),
            reason='Staff exception during pause',
        )
        account = fund_account(participant)
        product = ProductFactory(price=Decimal('5.00'), quantity_in_stock=50)

        OrderOrchestration().create_order(
            account=account,
            order_items_data=[OrderItemData(product=product, quantity=1)],
            user=participant.user,
        )
        assert Order.objects.filter(account=account, status='pending').count() == 1

    def test_force_closed_override_does_not_unblock_pause(self, participant):
        """Only a force-OPEN override is the escape hatch."""
        create_in_progress_pause()
        ProgramWindowOverride.objects.create(
            program=participant.program,
            force_status='closed',
            expires_at=timezone.now() + timedelta(hours=4),
            reason='Closed anyway',
        )
        account = fund_account(participant)
        product = ProductFactory(price=Decimal('5.00'), quantity_in_stock=50)

        with pytest.raises(ValidationError, match='program pause'):
            OrderOrchestration().create_order(
                account=account,
                order_items_data=[OrderItemData(product=product, quantity=1)],
                user=participant.user,
            )

    def test_validate_order_items_blocked_directly(self, participant):
        create_in_progress_pause()
        account = fund_account(participant)
        product = ProductFactory(price=Decimal('5.00'), quantity_in_stock=50)

        with pytest.raises(ValidationError, match='program pause'):
            OrderValidation().validate_order_items(
                [OrderItemData(product=product, quantity=1)],
                participant,
                account,
            )


# ---------------------------------------------------------------------------
# validate-cart endpoint
# ---------------------------------------------------------------------------

class TestValidateCartDuringPause:
    endpoint = '/api/v1/orders/validate-cart/'

    def _post_cart(self, participant, product):
        client = APIClient()
        client.force_authenticate(user=participant.user)
        return client.post(
            self.endpoint,
            {'items': [{'product_id': product.id, 'quantity': 1}]},
            format='json',
        )

    def test_validate_cart_reports_window_violation_during_pause(self, participant):
        create_in_progress_pause()
        fund_account(participant)
        product = ProductFactory(price=Decimal('5.00'), quantity_in_stock=50)

        response = self._post_cart(participant, product)

        assert response.status_code == 200
        assert response.data['valid'] is False
        window_violations = [
            v for v in response.data['violations'] if v['type'] == 'window'
        ]
        assert len(window_violations) == 1
        assert window_violations[0]['severity'] == 'error'

    def test_validate_cart_has_no_window_violation_without_pause(self, participant):
        fund_account(participant)
        product = ProductFactory(price=Decimal('5.00'), quantity_in_stock=50)

        response = self._post_cart(participant, product)

        assert response.status_code == 200
        assert all(v['type'] != 'window' for v in response.data['violations'])
