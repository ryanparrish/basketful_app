"""Tests for the inventory report (Issue #143).

Data rules are tested on apps.orders.inventory_report directly; the API
the React admin uses is /api/v1/reports/inventory/.

The centrepiece is a spot check: a known set of orders in a known week,
with the report's three tables verified against hand-computed numbers —
item quantities, cost by program, and the distinct participant count.
"""
import csv
import io
from datetime import date, datetime, time, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.utils import timezone

from apps.account.models import AccountBalance
from apps.account.tests.helpers import password_already_chosen
from apps.orders.models import Order, OrderItem
from apps.orders.tests.factories import (
    ParticipantFactory,
    ProductFactory,
    ProgramFactory,
)
from apps.orders.inventory_report import (
    COUNTED_STATUSES,
    _csv_safe,
    _get_date_range,
    _get_inventory_data,
)
from apps.pantry.models import Category, Subcategory
from apps.voucher.models import VoucherSetting

User = get_user_model()

# Monday Nov 2, 2026 through Sunday Nov 8, 2026 — one full week.
WEEK_START = date(2026, 11, 2)
WEEK_END = date(2026, 11, 8)


def _set_order_date(order, day, hour=12):
    """Place an order on a specific local date (order_date is auto_now_add)."""
    dt = timezone.make_aware(datetime.combine(day, time(hour, 0)))
    Order.objects.filter(pk=order.pk).update(order_date=dt)
    order.refresh_from_db()
    return order


def _make_order(account, status, day, items):
    """Create an order with items: [(product, quantity, price_at_order)]."""
    order = Order.objects.create(account=account, status=status)
    _set_order_date(order, day)
    for product, quantity, price_at_order in items:
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            price_at_order=price_at_order,
        )
    return order


@pytest.fixture
def voucher_setting(db):
    VoucherSetting.objects.all().update(active=False)
    return VoucherSetting.objects.create(
        adult_amount=Decimal('20.00'),
        child_amount=Decimal('12.50'),
        infant_modifier=Decimal('0.00'),
        active=True,
    )


@pytest.fixture
def staff_user(db):
    with patch('apps.pantry.signals.send_new_user_onboarding_email.delay'):
        return password_already_chosen(User.objects.create_user(
            username='staffer', password='testpass123', is_staff=True
        ))


@pytest.fixture
def catalog(db):
    dairy = Category.objects.create(name='Dairy')
    milk_sub = Subcategory.objects.create(name='Milk', category=dairy)
    canned = Category.objects.create(name='Canned Goods')
    milk = ProductFactory(
        name='Whole Milk', price=Decimal('2.50'),
        category=dairy, subcategory=milk_sub,
    )
    soup = ProductFactory(
        name='Canned Soup', price=Decimal('1.25'),
        category=canned, subcategory=None,
    )
    return milk, soup


@pytest.fixture
def known_week(db, voucher_setting, catalog):
    """
    Orders in the week Mon Nov 2 - Sun Nov 8, 2026:

    Counted (confirmed / packing / completed):
    - Participant A (Program One), completed Mon Nov 2:
        4x Milk @2.50, 2x Soup @1.25  -> $12.50
    - Participant A (Program One), completed Wed Nov 4:
        1x Milk @2.50                 -> $2.50
    - Participant B (Program One), confirmed Wed Nov 4:
        2x Milk @2.50                 -> $5.00
    - Participant C (Program Two), packing Fri Nov 6:
        1x Soup @1.25                 -> $1.25
    - Participant B (Program One), completed Sun Nov 8 (end date):
        1x Soup @1.25                 -> $1.25

    Not counted:
    - Participant A, pending Tue Nov 3:   10x Milk
    - Participant B, cancelled Thu Nov 5: 10x Soup
    - Participant C, completed Sun Nov 1 (day before the range): 5x Milk
    - Participant C, completed Mon Nov 9 (day after the range):  3x Milk

    Expected for Nov 2-8, whole-range grouping:
    - Items: Milk qty 7 / $17.50; Soup qty 4 / $5.00 (sorted Milk first)
    - Cost: Program One $21.25, Program Two $1.25, grand total $22.50
    - Participants that week: 3 (A, B, C — A counted once despite 2 orders)
    """
    milk, soup = catalog
    program_one = ProgramFactory(name='Program One')
    program_two = ProgramFactory(name='Program Two')

    def account_for(name, program):
        participant = ParticipantFactory(name=name, program=program)
        return AccountBalance.objects.get(participant=participant)

    acct_a = account_for('Participant A', program_one)
    acct_b = account_for('Participant B', program_one)
    acct_c = account_for('Participant C', program_two)

    _make_order(acct_a, 'completed', date(2026, 11, 2),
                [(milk, 4, Decimal('2.50')), (soup, 2, Decimal('1.25'))])
    _make_order(acct_a, 'completed', date(2026, 11, 4),
                [(milk, 1, Decimal('2.50'))])
    _make_order(acct_b, 'confirmed', date(2026, 11, 4),
                [(milk, 2, Decimal('2.50'))])
    _make_order(acct_c, 'packing', date(2026, 11, 6),
                [(soup, 1, Decimal('1.25'))])
    _make_order(acct_b, 'completed', date(2026, 11, 8),
                [(soup, 1, Decimal('1.25'))])

    _make_order(acct_a, 'pending', date(2026, 11, 3),
                [(milk, 10, Decimal('2.50'))])
    _make_order(acct_b, 'cancelled', date(2026, 11, 5),
                [(soup, 10, Decimal('1.25'))])
    _make_order(acct_c, 'completed', date(2026, 11, 1),
                [(milk, 5, Decimal('2.50'))])
    _make_order(acct_c, 'completed', date(2026, 11, 9),
                [(milk, 3, Decimal('2.50'))])

    return {
        'milk': milk, 'soup': soup,
        'program_one': program_one, 'program_two': program_two,
    }


class TestSpotCheckKnownWeek:
    """Acceptance: report numbers match raw orders for a known week."""

    def test_items_table(self, known_week):
        data = _get_inventory_data(WEEK_START, WEEK_END)
        items = data['items']
        assert [row['product_name'] for row in items] == [
            'Whole Milk', 'Canned Soup',
        ]
        milk_row, soup_row = items
        assert milk_row['quantity'] == 7
        assert milk_row['total_cost'] == Decimal('17.50')
        assert milk_row['category'] == 'Dairy'
        assert milk_row['subcategory'] == 'Milk'
        assert soup_row['quantity'] == 4
        assert soup_row['total_cost'] == Decimal('5.00')
        assert soup_row['category'] == 'Canned Goods'
        assert soup_row['subcategory'] == ''

    def test_cost_by_program_and_grand_total(self, known_week):
        data = _get_inventory_data(WEEK_START, WEEK_END)
        costs = {
            row['program_name']: row['total_cost']
            for row in data['program_costs']
        }
        assert costs == {
            'Program One': Decimal('21.25'),
            'Program Two': Decimal('1.25'),
        }
        assert data['grand_total'] == Decimal('22.50')

    def test_participants_per_week_distinct(self, known_week):
        data = _get_inventory_data(WEEK_START, WEEK_END)
        rows = data['participants_per_week']
        assert len(rows) == 1
        assert rows[0]['week_start'] == date(2026, 11, 2)
        assert rows[0]['week_end'] == date(2026, 11, 8)
        # A placed two counted orders but is counted once.
        assert rows[0]['participant_count'] == 3


class TestStatusFiltering:
    def test_only_counted_statuses(self, db, voucher_setting, catalog):
        milk, _soup = catalog
        participant = ParticipantFactory(name='Solo')
        account = AccountBalance.objects.get(participant=participant)
        for status in ('pending', 'cancelled'):
            _make_order(account, status, date(2026, 11, 3),
                        [(milk, 5, Decimal('2.50'))])
        data = _get_inventory_data(WEEK_START, WEEK_END)
        assert data['items'] == []
        assert data['grand_total'] == Decimal('0.00')
        assert data['participants_per_week'][0]['participant_count'] == 0

    def test_counted_statuses_constant(self):
        assert set(COUNTED_STATUSES) == {'confirmed', 'packing', 'completed'}


class TestDateRangeInclusivity:
    def test_boundary_days(self, known_week):
        # Nov 1 and Nov 9 orders exist in the fixture; a range covering
        # only Nov 2-8 must exclude them (verified by the spot check),
        # while widening the range pulls them in.
        wide = _get_inventory_data(date(2026, 11, 1), date(2026, 11, 9))
        milk_row = next(
            r for r in wide['items'] if r['product_name'] == 'Whole Milk'
        )
        assert milk_row['quantity'] == 7 + 5 + 3
        weeks = wide['participants_per_week']
        assert [w['week_start'] for w in weeks] == [
            date(2026, 10, 26), date(2026, 11, 2), date(2026, 11, 9),
        ]


class TestGrouping:
    def test_weekly_grouping_monday_start(self, known_week):
        data = _get_inventory_data(
            date(2026, 11, 2), date(2026, 11, 15), grouping='weekly'
        )
        milk_rows = [
            r for r in data['items'] if r['product_name'] == 'Whole Milk'
        ]
        assert len(milk_rows) == 2
        assert milk_rows[0]['period_label'] == '2026-11-02 to 2026-11-08'
        assert milk_rows[0]['quantity'] == 7
        assert milk_rows[1]['period_label'] == '2026-11-09 to 2026-11-15'
        assert milk_rows[1]['quantity'] == 3
        # Weeks start on Monday.
        for row in data['participants_per_week']:
            assert row['week_start'].weekday() == 0
            assert row['week_end'] == row['week_start'] + timedelta(days=6)

    def test_monthly_grouping(self, db, voucher_setting, catalog):
        milk, _soup = catalog
        participant = ParticipantFactory(name='Monthly')
        account = AccountBalance.objects.get(participant=participant)
        _make_order(account, 'completed', date(2026, 11, 20),
                    [(milk, 2, Decimal('2.50'))])
        _make_order(account, 'completed', date(2026, 12, 3),
                    [(milk, 5, Decimal('2.50'))])
        data = _get_inventory_data(
            date(2026, 11, 1), date(2026, 12, 31), grouping='monthly'
        )
        labels = [r['period_label'] for r in data['items']]
        assert labels == ['November 2026', 'December 2026']
        assert [r['quantity'] for r in data['items']] == [2, 5]


class TestProgramFilter:
    def test_filter_to_one_program(self, known_week):
        data = _get_inventory_data(
            WEEK_START, WEEK_END, program=known_week['program_two']
        )
        assert [r['product_name'] for r in data['items']] == ['Canned Soup']
        assert data['items'][0]['quantity'] == 1
        assert data['grand_total'] == Decimal('1.25')
        assert data['participants_per_week'][0]['participant_count'] == 1


class TestPriceFallback:
    def test_missing_price_at_order_falls_back_to_price(
        self, db, voucher_setting, catalog
    ):
        milk, _soup = catalog
        participant = ParticipantFactory(name='Legacy')
        account = AccountBalance.objects.get(participant=participant)
        order = _make_order(account, 'completed', date(2026, 11, 3),
                            [(milk, 2, Decimal('2.50'))])
        # Simulate a pre-snapshot row: no price_at_order, price = $3.00.
        OrderItem.objects.filter(order=order).update(
            price_at_order=None, price=Decimal('3.00')
        )
        data = _get_inventory_data(WEEK_START, WEEK_END)
        assert data['items'][0]['total_cost'] == Decimal('6.00')
        assert data['grand_total'] == Decimal('6.00')


class TestDateRangeHelper:
    def test_last_6_months_preset(self):
        start, end = _get_date_range('last_6_months')
        assert end == timezone.localdate()
        assert start < end
        # Roughly six months back (same day-of-month, clamped).
        assert (end - start).days >= 180

    def test_custom_passthrough(self):
        start, end = _get_date_range(
            'custom', date(2026, 1, 5), date(2026, 2, 5)
        )
        assert (start, end) == (date(2026, 1, 5), date(2026, 2, 5))


REPORT_URL = '/api/v1/reports/inventory/'
KNOWN_WEEK_PARAMS = {'date_range': 'custom', 'start_date': '2026-11-02',
                     'end_date': '2026-11-08', 'grouping': 'range'}


def _api(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


class TestReportApi:
    def test_staff_gets_known_week_numbers(self, db, staff_user, known_week):
        response = _api(staff_user).get(REPORT_URL, KNOWN_WEEK_PARAMS)
        assert response.status_code == 200, response.data
        data = response.data
        assert data['start_date'] == '2026-11-02'
        assert data['end_date'] == '2026-11-08'
        milk = next(r for r in data['items']
                    if r['product_name'] == 'Whole Milk')
        assert milk['quantity'] == 7
        assert milk['total_cost'] == '17.50'
        costs = {r['program_name']: r['total_cost']
                 for r in data['program_costs']}
        assert costs == {'Program One': '21.25', 'Program Two': '1.25'}
        assert data['grand_total'] == '22.50'
        week = data['participants_per_week'][0]
        assert week['week_start'] == '2026-11-02'
        assert week['participant_count'] == 3
        assert week['is_partial'] is False

    def test_program_filter(self, db, staff_user, known_week):
        response = _api(staff_user).get(REPORT_URL, {
            **KNOWN_WEEK_PARAMS, 'program': known_week['program_two'].pk,
        })
        assert response.status_code == 200
        assert response.data['grand_total'] == '1.25'
        assert response.data['program_name'] == 'Program Two'

    def test_defaults_to_last_6_months(self, db, staff_user):
        response = _api(staff_user).get(REPORT_URL)
        assert response.status_code == 200
        assert response.data['end_date'] == timezone.localdate().isoformat()
        assert response.data['grouping'] == 'range'

    @pytest.mark.parametrize('params, field', [
        ({'date_range': 'custom'}, 'start_date'),
        ({'date_range': 'custom', 'start_date': '2026-11-08',
          'end_date': '2026-11-02'}, 'end_date'),
        ({'date_range': 'custom', 'start_date': '0026-01-01',
          'end_date': '2026-11-02'}, 'end_date'),
        ({'grouping': 'daily'}, 'grouping'),
        ({'program': 999999}, 'program'),
    ])
    def test_bad_params_are_400s(self, db, staff_user, params, field):
        response = _api(staff_user).get(REPORT_URL, params)
        assert response.status_code == 400
        assert field in response.data

    def test_non_staff_and_anonymous_refused(self, db):
        with patch('apps.pantry.signals.send_new_user_onboarding_email.delay'):
            plain = User.objects.create_user(
                username='plain', password='testpass123'
            )
        assert _api(plain).get(REPORT_URL).status_code == 403
        assert _api().get(REPORT_URL).status_code in (401, 403)

    def test_csv_matches_json_numbers(self, db, staff_user, known_week):
        client = _api(staff_user)
        json_data = client.get(REPORT_URL, KNOWN_WEEK_PARAMS).data
        response = client.get(REPORT_URL, {**KNOWN_WEEK_PARAMS, 'export': 'csv'})
        assert response.status_code == 200
        assert response['Content-Type'] == 'text/csv'
        assert 'attachment' in response['Content-Disposition']

        rows = list(csv.reader(io.StringIO(response.content.decode())))
        flat = [cell for row in rows for cell in row]
        for item in json_data['items']:
            assert item['product_name'] in flat
            assert str(item['quantity']) in flat
            assert item['total_cost'] in flat
        for cost in json_data['program_costs']:
            assert cost['program_name'] in flat
            assert cost['total_cost'] in flat
        assert json_data['grand_total'] in flat
        week_row = next(r for r in rows if r and r[0] == '2026-11-02')
        assert week_row == ['2026-11-02', '2026-11-08', '3', '']


# ---------------------------------------------------------------------------
# Review fixes
# ---------------------------------------------------------------------------

class TestPartialWeeks:
    def test_mid_week_range_flags_partial_weeks(self, known_week):
        # Wed Nov 4 to Tue Nov 10: both weeks are cut short.
        data = _get_inventory_data(date(2026, 11, 4), date(2026, 11, 10))
        first, last = data['participants_per_week']
        assert first['is_partial'] and last['is_partial']
        assert first['counted_from'] == date(2026, 11, 4)
        assert first['counted_to'] == date(2026, 11, 8)
        assert last['counted_from'] == date(2026, 11, 9)
        assert last['counted_to'] == date(2026, 11, 10)

    def test_full_week_is_not_partial(self, known_week):
        data = _get_inventory_data(WEEK_START, WEEK_END)
        assert data['participants_per_week'][0]['is_partial'] is False

    def test_weekly_item_label_shows_counted_days(self, known_week):
        data = _get_inventory_data(
            date(2026, 11, 4), date(2026, 11, 8), grouping='weekly'
        )
        labels = {r['period_label'] for r in data['items']}
        assert labels == {'2026-11-04 to 2026-11-08 (partial week)'}

    def test_csv_notes_partial_week(self, db, staff_user, known_week):
        response = _api(staff_user).get(REPORT_URL, {
            'date_range': 'custom', 'start_date': '2026-11-04',
            'end_date': '2026-11-08', 'grouping': 'range', 'export': 'csv',
        })
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        week_row = next(r for r in rows if r and r[0] == '2026-11-02')
        assert week_row[3] == (
            'Partial week: counts 2026-11-04 to 2026-11-08 only'
        )


class TestLocalToday:
    def test_presets_use_local_date_not_server_date(self):
        # 11:30pm Eastern on Sat Nov 7 is already Nov 8 in UTC.
        late_evening_utc = datetime(2026, 11, 8, 4, 30, tzinfo=dt_timezone.utc)
        with patch('django.utils.timezone.now', return_value=late_evening_utc):
            start, end = _get_date_range('this_week')
        assert end == date(2026, 11, 7)
        assert start == date(2026, 11, 2)


class TestCsvSafety:
    @pytest.mark.parametrize('value', ['=1+1', '+SUM(A1)', '-2', '@cmd'])
    def test_formula_like_cells_are_escaped(self, value):
        assert _csv_safe(value) == "'" + value

    def test_plain_text_untouched(self):
        assert _csv_safe('Whole Milk') == 'Whole Milk'
        assert _csv_safe(7) == 7
