"""
#156: GET /api/v1/participants/ (participant list) must cost the same number
of queries whatever the page size. Each row used to compute its balances with
about 11 queries of its own (the account, vouchers, program pauses, hygiene
and Go Fresh settings, with the available balance computed twice), so a full
page took over a second in production.

The list now loads every row's account and open grocery vouchers up front and
the global settings once per request. Its balances must still match
Participant.balances() exactly — this is money.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.account.models import AccountBalance, HygieneSettings, Participant
from apps.lifeskills.models import ProgramPause
from apps.orders.tests.factories import ParticipantFactory, UserFactory, VoucherSettingFactory
from apps.voucher.models import Voucher

BALANCE_FIELDS = ('full_balance', 'available_balance', 'hygiene_balance', 'go_fresh_balance')


@pytest.fixture(autouse=True)
def voucher_setting():
    return VoucherSettingFactory(active=True)


@pytest.fixture
def staff_client():
    client = APIClient()
    client.force_authenticate(user=UserFactory(is_staff=True))
    return client


@pytest.fixture
def active_double_week_pause():
    """A pause whose gate window is open now, doubling balances (multiplier 2)."""
    pause_start = timezone.now() + timedelta(days=12)
    return ProgramPause.objects.create(
        pause_start=pause_start,
        pause_end=pause_start + timedelta(days=5),
        reason='Test pause',
    )


def participant_with_vouchers(voucher_states, base_balance=Decimal('100.00'), **participant_fields):
    """A participant whose only vouchers are grocery vouchers in the given states."""
    participant = ParticipantFactory(**participant_fields)
    account = participant.accountbalance
    # Participant creation provisions starter vouchers; replace them.
    account.vouchers.all().delete()
    AccountBalance.objects.filter(pk=account.pk).update(base_balance=base_balance)
    for state in voucher_states:
        Voucher.objects.create(account=account, voucher_type='grocery', state=state)
    return participant


def list_participants(client):
    with CaptureQueriesContext(connection) as captured:
        response = client.get('/api/v1/participants/?page_size=100&active=true')
    assert response.status_code == 200, response.data
    rows = {row['id']: row for row in response.data['results']}
    return rows, captured


def expected_balances(participant):
    """Balances computed the per-participant way, with fresh queries."""
    return Participant.objects.get(pk=participant.pk).balances()


@pytest.mark.django_db
class TestParticipantListQueries:

    def test_query_count_does_not_grow_with_participants(self, staff_client):
        participant_with_vouchers(['applied', 'applied'])
        list_participants(staff_client)  # first call creates the settings rows
        _, few_queries = list_participants(staff_client)

        for _ in range(10):
            participant_with_vouchers(['applied', 'applied', 'pending'])
        rows, many_queries = list_participants(staff_client)

        assert len(rows) == 11
        assert len(many_queries) == len(few_queries)


@pytest.mark.django_db
class TestParticipantListBalances:

    def test_balances_match_per_participant_calculation(
        self, staff_client, active_double_week_pause
    ):
        participants = [
            # More than 2 applied vouchers: only the oldest 2 are available.
            participant_with_vouchers(
                ['applied', 'applied', 'applied', 'pending', 'consumed', 'expired'],
                adults=1, children=0,
            ),
            participant_with_vouchers(['pending'], adults=2, children=2),
            participant_with_vouchers([], adults=4, children=3),
            participant_with_vouchers(['applied'], base_balance=Decimal('35.50'), adults=1, children=1),
        ]

        rows, _ = list_participants(staff_client)

        for participant in participants:
            assert rows[participant.id]['balances'] == expected_balances(participant)

    def test_balances_have_expected_values(self, staff_client, active_double_week_pause):
        """Pin the numbers so the parity check above is not comparing a bug with itself."""
        small = participant_with_vouchers(
            ['applied', 'applied', 'applied', 'pending', 'consumed'], adults=1, children=0,
        )
        medium = participant_with_vouchers(['applied'], adults=2, children=2)
        large = participant_with_vouchers([], adults=4, children=3)

        rows, _ = list_participants(staff_client)

        assert rows[small.id]['balances'] == {
            'full_balance': Decimal('400.00'),       # 3 applied + 1 pending × $100
            'available_balance': Decimal('400.00'),  # oldest 2 applied × $100 × 2
            'hygiene_balance': Decimal('134'),       # ⅓ of 400, rounded up
            'go_fresh_balance': Decimal('20.00'),    # small household $10 × 2
        }
        assert rows[medium.id]['balances']['go_fresh_balance'] == Decimal('40.00')
        assert rows[large.id]['balances']['go_fresh_balance'] == Decimal('50.00')
        assert rows[large.id]['balances']['available_balance'] == 0

    def test_hygiene_disabled_reports_zero(self, staff_client):
        participant = participant_with_vouchers(['applied', 'applied'])
        HygieneSettings.objects.filter(pk=HygieneSettings.get_settings().pk).update(enabled=False)

        rows, _ = list_participants(staff_client)

        assert rows[participant.id]['balances']['hygiene_balance'] == 0
        assert rows[participant.id]['balances'] == expected_balances(participant)

    def test_participant_without_account(self, staff_client):
        participant = ParticipantFactory()
        AccountBalance.objects.filter(participant=participant).delete()

        rows, _ = list_participants(staff_client)

        row = rows[participant.id]
        assert row['balances'] == {field: 0 for field in BALANCE_FIELDS}
        assert row['balances'] == expected_balances(participant)
        assert row['has_account'] is False
        assert row['account_balance_id'] is None
        assert row['base_balance'] == '0'

    def test_account_fields_still_reported(self, staff_client):
        participant = participant_with_vouchers(['applied'])

        rows, _ = list_participants(staff_client)

        row = rows[participant.id]
        assert row['has_account'] is True
        assert row['account_balance_id'] == participant.accountbalance.id
        assert row['base_balance'] == '100.00'
