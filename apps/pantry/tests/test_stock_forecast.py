"""
Tests for the stock forecast (Issue #148).

Order history is built week by week relative to today, using the same
Monday-week helper as the forecast, so expected numbers are exact:

- weekly usage is a recent-weighted average of usable weeks
  (weight 1 for the oldest week in the window up to 12 for last week)
- available = stock on hand - units on pending orders (only pending)
- weeks left = available / weekly usage; reorder covers cover + safety weeks
- weeks are left out when a snapshot shows the product out of stock or
  inactive, when they're before the product existed, or when they're the
  run of zero weeks up to now for a product that's out of stock now
"""
from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.account.models import AccountBalance
from apps.account.tests.helpers import password_already_chosen
from apps.orders.models import Order, OrderItem
from apps.orders.tests.factories import ParticipantFactory, ProductFactory
from apps.pantry.forecast import (
    STATUS_CRITICAL,
    STATUS_INSUFFICIENT,
    STATUS_LOW,
    STATUS_OK,
    compute_forecast,
    history_weeks_for,
)
from apps.pantry.models import (
    LowInventoryAlertSettings,
    Product,
    ProductStockSnapshot,
)
from apps.pantry.tasks.stock_forecast import (
    check_stock_forecast,
    record_stock_snapshots,
)
from apps.voucher.models import VoucherSetting

pytestmark = pytest.mark.django_db

User = get_user_model()
URL = '/api/v1/reports/stock-forecast/'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def voucher_setting(db):
    VoucherSetting.objects.all().update(active=False)
    return VoucherSetting.objects.create(
        adult_amount=Decimal('20.00'), child_amount=Decimal('12.50'),
        infant_modifier=Decimal('0.00'), active=True,
    )


@pytest.fixture
def today():
    return timezone.localdate()


@pytest.fixture
def weeks(today):
    """The 12 complete weeks in the default window, oldest first."""
    return history_weeks_for(today, 12)


@pytest.fixture
def account(db):
    participant = ParticipantFactory(name='Forecast Participant')
    return AccountBalance.objects.get(participant=participant)


def _aware(day, hour=12):
    return timezone.make_aware(datetime.combine(day, time(hour, 0)))


def make_product(name, stock, *, active=True, created_weeks_ago=30):
    product = ProductFactory(name=name, price=Decimal('1.00'))
    Product.objects.filter(pk=product.pk).update(
        quantity_in_stock=stock, active=active,
        created_at=timezone.now() - timedelta(weeks=created_weeks_ago),
    )
    product.refresh_from_db()
    return product


def order_units(account, product, day, units, status='completed'):
    """One order on ``day`` with ``units`` of ``product``."""
    order = Order.objects.create(account=account, status='completed')
    Order.objects.filter(pk=order.pk).update(order_date=_aware(day))
    OrderItem.objects.create(
        order=order, product=product, quantity=units,
        price_at_order=product.price,
    )
    if status != 'completed':
        Order.objects.filter(pk=order.pk).update(status=status)
    return order


def weekly_history(account, product, weeks, units_per_week):
    """``units_per_week``: one number per week (oldest first); 0 = no order."""
    for monday, units in zip(weeks, units_per_week):
        if units:
            order_units(account, product, monday + timedelta(days=1), units)


def restore_stock(product, stock, active=True):
    """Orders don't move stock here, but set it explicitly to be sure."""
    Product.objects.filter(pk=product.pk).update(
        quantity_in_stock=stock, active=active,
    )


def row_for(product, **kwargs):
    rows = compute_forecast(product_ids=[product.pk], **kwargs)
    assert len(rows) == 1
    return rows[0]


@pytest.fixture
def staff_user(db):
    with patch('apps.pantry.signals.send_new_user_onboarding_email.delay'):
        return password_already_chosen(User.objects.create_user(
            username='pantry-admin', password='x', is_staff=True,
            email='pantry-admin@example.com',
        ))


def _api(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


# ---------------------------------------------------------------------------
# The calculation
# ---------------------------------------------------------------------------

class TestForecastNumbers:

    def test_steady_usage(self, account, weeks, today):
        soup = make_product('Canned Soup', 0)
        weekly_history(account, soup, weeks, [10] * 12)
        restore_stock(soup, 40)

        row = row_for(soup)
        assert row['usable_weeks'] == 12
        assert row['weekly_usage'] == 10.0
        assert row['available'] == 40
        assert row['weeks_left'] == 4.0
        assert row['runout_date'] == today + timedelta(days=28)
        # Cover 4 + safety 1 weeks at 10/week = 50, minus 40 available.
        assert row['suggested_reorder'] == 10
        assert row['status'] == STATUS_LOW  # 4 weeks left <= 4-week cover
        assert '10/week' in row['explanation']
        assert len(row['history']) == 12

    def test_recent_weeks_count_more(self, account, weeks):
        beans = make_product('Black Beans', 0)
        weekly_history(account, beans, weeks, [5] * 6 + [15] * 6)
        restore_stock(beans, 100)
        # Plain average would be 10; weights 1..12 give 960 / 78 = 12.3.
        assert row_for(beans)['weekly_usage'] == 12.3

    def test_snapshot_out_of_stock_weeks_are_left_out(self, account, weeks):
        milk = make_product('Whole Milk', 0)
        units = [10] * 12
        for out_week in (3, 4, 5):
            units[out_week] = 0
            ProductStockSnapshot.objects.create(
                product=milk, date=weeks[out_week] + timedelta(days=2),
                quantity_in_stock=0, active=False,
            )
        weekly_history(account, milk, weeks, units)
        restore_stock(milk, 50)

        row = row_for(milk)
        assert row['usable_weeks'] == 9
        assert row['weekly_usage'] == 10.0  # not dragged down by the 0s
        excluded = [w for w in row['history'] if not w['usable']]
        assert len(excluded) == 3
        assert all('out of stock' in w['excluded_reason'] for w in excluded)

    def test_trailing_zero_weeks_while_out_now_are_left_out(self, account, weeks):
        rice = make_product('Rice', 0)
        weekly_history(account, rice, weeks, [10] * 9 + [0, 0, 0])
        restore_stock(rice, 0, active=False)  # ran out, auto-deactivated

        row = row_for(rice)
        assert row['usable_weeks'] == 9
        assert row['weekly_usage'] == 10.0
        assert row['weeks_left'] == 0.0
        assert row['status'] == STATUS_CRITICAL
        assert row['suggested_reorder'] == 50
        assert 'Out of stock now' in row['explanation']

    def test_trailing_zero_weeks_count_when_in_stock(self, account, weeks):
        # In stock now, so recent zero weeks are genuine zero demand.
        pasta = make_product('Pasta', 0)
        weekly_history(account, pasta, weeks, [10] * 9 + [0, 0, 0])
        restore_stock(pasta, 30)
        assert row_for(pasta)['usable_weeks'] == 12

    def test_weeks_before_the_product_existed_are_left_out(self, account, weeks):
        apples = make_product('Apples', 0, created_weeks_ago=3)
        weekly_history(account, apples, weeks, [0] * 9 + [6, 6, 6])
        restore_stock(apples, 20)

        row = row_for(apples)
        assert row['usable_weeks'] == 3
        assert row['status'] == STATUS_INSUFFICIENT
        assert row['weekly_usage'] is None
        assert row['suggested_reorder'] is None
        assert 'needs 4' in row['explanation']

    def test_pending_orders_subtracted_once(self, account, weeks, today):
        soup = make_product('Canned Soup', 0)
        weekly_history(account, soup, weeks, [10] * 12)
        other = AccountBalance.objects.get(
            participant=ParticipantFactory(name='Pending Person')
        )
        order_units(other, soup, today, 5, status='pending')
        # A confirmed order this week already took its units off the shelf
        # (stock below reflects that), so it must not be subtracted again.
        third = AccountBalance.objects.get(
            participant=ParticipantFactory(name='Confirmed Person')
        )
        order_units(third, soup, today, 7, status='confirmed')
        restore_stock(soup, 40)

        row = row_for(soup)
        assert row['pending_units'] == 5
        assert row['available'] == 35
        assert row['weeks_left'] == 3.5

    def test_status_bands(self, account, weeks):
        plenty = make_product('Plenty', 0)
        tight = make_product('Tight', 0)
        weekly_history(account, plenty, weeks, [10] * 12)
        weekly_history(account, tight, weeks, [10] * 12)
        restore_stock(plenty, 100)  # 10 weeks
        restore_stock(tight, 8)     # 0.8 weeks
        assert row_for(plenty)['status'] == STATUS_OK
        assert row_for(plenty)['suggested_reorder'] == 0
        assert row_for(tight)['status'] == STATUS_CRITICAL

    def test_no_demand_is_ok_without_weeks_left(self, weeks):
        idle = make_product('Idle', 25)
        row = row_for(idle)
        assert row['status'] == STATUS_OK
        assert row['weekly_usage'] == 0.0
        assert row['weeks_left'] is None
        assert 'No recent demand' in row['explanation']

    def test_most_urgent_first_and_discontinued_skipped(self, account, weeks):
        plenty = make_product('Plenty', 0)
        tight = make_product('Tight', 0)
        make_product('Discontinued', 0, active=False)
        weekly_history(account, plenty, weeks, [10] * 12)
        weekly_history(account, tight, weeks, [10] * 12)
        restore_stock(plenty, 100)
        restore_stock(tight, 8)
        names = [r['product_name'] for r in compute_forecast()]
        assert names.index('Tight') < names.index('Plenty')
        assert 'Discontinued' not in names


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

class TestForecastApi:

    def test_staff_gets_forecast(self, staff_user, account, weeks):
        soup = make_product('Canned Soup', 0)
        weekly_history(account, soup, weeks, [10] * 12)
        restore_stock(soup, 40)
        response = _api(staff_user).get(URL)
        assert response.status_code == 200, response.data
        assert response.data['history_weeks'] == 12
        row = next(r for r in response.data['results']
                   if r['product_name'] == 'Canned Soup')
        assert row['weeks_left'] == 4.0
        assert isinstance(row['runout_date'], str)
        assert row['history'][0]['week_start'] == weeks[0].isoformat()

    def test_one_product_and_status_filter(self, staff_user, account, weeks):
        soup = make_product('Canned Soup', 0)
        make_product('Other', 30)
        weekly_history(account, soup, weeks, [10] * 12)
        restore_stock(soup, 5)
        client = _api(staff_user)
        one = client.get(URL, {'product': soup.pk}).data['results']
        assert [r['product_name'] for r in one] == ['Canned Soup']
        critical = client.get(URL, {'status': 'critical'}).data['results']
        assert [r['product_name'] for r in critical] == ['Canned Soup']

    def test_settings_change_the_numbers(self, staff_user, account, weeks):
        soup = make_product('Canned Soup', 0)
        weekly_history(account, soup, weeks, [10] * 12)
        restore_stock(soup, 40)
        row = _api(staff_user).get(
            URL, {'product': soup.pk, 'cover_weeks': 8, 'safety_weeks': 2}
        ).data['results'][0]
        assert row['suggested_reorder'] == 60  # 10 x (8 + 2) - 40

    @pytest.mark.parametrize('params, field', [
        ({'history_weeks': 2}, 'history_weeks'),
        ({'cover_weeks': 0}, 'cover_weeks'),
        ({'status': 'panic'}, 'status'),
        ({'product': 999999}, 'product'),
    ])
    def test_bad_params_are_400s(self, staff_user, params, field):
        response = _api(staff_user).get(URL, params)
        assert response.status_code == 400
        assert field in response.data

    def test_non_staff_refused(self, db):
        with patch('apps.pantry.signals.send_new_user_onboarding_email.delay'):
            plain = User.objects.create_user(username='plain', password='x')
        assert _api(plain).get(URL).status_code == 403
        assert _api().get(URL).status_code in (401, 403)

    def test_reorder_csv_lists_only_products_to_reorder(
        self, staff_user, account, weeks
    ):
        soup = make_product('=Canned Soup', 0)
        plenty = make_product('Plenty', 0)
        weekly_history(account, soup, weeks, [10] * 12)
        weekly_history(account, plenty, weeks, [10] * 12)
        restore_stock(soup, 40)
        restore_stock(plenty, 100)
        response = _api(staff_user).get(URL, {'export': 'csv'})
        assert response.status_code == 200
        assert response['Content-Type'] == 'text/csv'
        body = response.content.decode()
        assert "'=Canned Soup" in body  # formula escaped
        assert 'Plenty' not in body
        assert 'Suggested reorder' in body

    def test_product_list_carries_forecast_for_staff(
        self, staff_user, account, weeks
    ):
        soup = make_product('Canned Soup', 0)
        weekly_history(account, soup, weeks, [10] * 12)
        restore_stock(soup, 40)
        response = _api(staff_user).get('/api/v1/products/', {'search': 'Canned Soup'})
        row = response.data['results'][0]
        assert row['forecast_weeks_left'] == 4.0
        assert row['forecast_status'] == STATUS_LOW


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------

class TestSnapshots:

    def test_keeps_lowest_stock_and_any_inactive_per_day(self, today):
        product = make_product('Milk', 10)
        record_stock_snapshots()
        Product.objects.filter(pk=product.pk).update(quantity_in_stock=0, active=False)
        record_stock_snapshots()
        Product.objects.filter(pk=product.pk).update(quantity_in_stock=30, active=True)
        record_stock_snapshots()

        snap = ProductStockSnapshot.objects.get(product=product, date=today)
        assert snap.quantity_in_stock == 0
        assert snap.active is False
        assert ProductStockSnapshot.objects.filter(product=product).count() == 1


# ---------------------------------------------------------------------------
# Alerts (existing low-inventory recipients + send_email_by_type)
# ---------------------------------------------------------------------------

DELAY = 'apps.account.tasks.email.send_email_by_type.delay'


@pytest.fixture
def alert_settings(staff_user):
    settings_obj = LowInventoryAlertSettings.get_settings()
    settings_obj.forecast_alerts_enabled = True
    settings_obj.forecast_alert_weeks = 1
    settings_obj.save()
    settings_obj.notify_groups.clear()
    settings_obj.notify_users.set([staff_user])
    return settings_obj


class TestForecastAlerts:

    def _tight_soup(self, account, weeks):
        soup = make_product('Canned Soup', 0)
        weekly_history(account, soup, weeks, [10] * 12)
        restore_stock(soup, 8)  # 0.8 weeks left
        return soup

    def test_disabled_sends_nothing(self, alert_settings, account, weeks):
        alert_settings.forecast_alerts_enabled = False
        alert_settings.save()
        self._tight_soup(account, weeks)
        with patch(DELAY) as delay:
            check_stock_forecast()
        delay.assert_not_called()

    def test_sends_one_digest_once(self, alert_settings, staff_user, account, weeks):
        soup = self._tight_soup(account, weeks)
        plenty = make_product('Plenty', 0)
        weekly_history(account, plenty, weeks, [10] * 12)
        restore_stock(plenty, 100)

        with patch(DELAY) as delay:
            check_stock_forecast()
        delay.assert_called_once()
        args, kwargs = delay.call_args
        assert args == (staff_user.pk, 'stock_forecast_alert')
        context = kwargs['extra_context']
        assert context['product_count'] == 1
        assert context['alert_weeks'] == 1
        assert context['products'][0]['name'] == 'Canned Soup'
        assert context['products'][0]['suggested_reorder'] == 42
        assert isinstance(context['products'][0]['runout_date'], str)
        soup.refresh_from_db()
        assert soup.forecast_alerted_at is not None

        with patch(DELAY) as delay:
            check_stock_forecast()
        delay.assert_not_called()  # same episode: no repeat

    def test_rearms_after_recovery(self, alert_settings, account, weeks):
        soup = self._tight_soup(account, weeks)
        with patch(DELAY):
            check_stock_forecast()
        restore_stock(soup, 200)
        with patch(DELAY) as delay:
            check_stock_forecast()
        delay.assert_not_called()
        soup.refresh_from_db()
        assert soup.forecast_alerted_at is None

    def test_settings_api_exposes_forecast_fields(self, staff_user):
        staff_user.is_superuser = True
        staff_user.save()
        response = _api(staff_user).get(
            '/api/v1/low-inventory-alert-settings/current/'
        )
        assert response.status_code == 200, response.data
        assert 'forecast_alerts_enabled' in response.data
        assert 'forecast_alert_weeks' in response.data
