"""
Tests for apps.pantry.tasks.low_inventory — low-inventory email alerts.

Business rules verified:
  1. A product at/below the threshold triggers one alert email per
     Inventory Manager, then never re-alerts while it stays low.
  2. Boundary: exactly at the threshold alerts; one above does not.
  3. Multiple newly-low products are grouped into a single email per
     recipient.
  4. A product that recovers above the threshold re-arms and alerts
     again on its next drop — regardless of how stock was mutated
     (queryset .update() bypassing save() included).
  5. Disabled settings, inactive products, and already-alerted products
     never trigger alerts.
  6. No emailable Inventory Managers → no dispatch, warning logged.
  7. LowInventoryAlertSettings enforces the singleton pattern.
  8. Full pipeline (no mocks): rendered email reaches mail.outbox and an
     EmailLog row is written for a staff user with no Participant.
"""
import logging
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from rest_framework.test import APIClient

from apps.log.models import EmailLog, EmailType
from apps.pantry.models import LowInventoryAlertSettings, Product
from apps.pantry.tasks.low_inventory import (
    INVENTORY_MANAGERS_GROUP,
    check_low_inventory,
)
from apps.pantry.tests.factories import ProductFactory

User = get_user_model()

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def alert_settings(db):
    """Singleton with the default threshold of 45, enabled."""
    return LowInventoryAlertSettings.get_settings()


@pytest.fixture
def inventory_managers(db):
    """The Inventory Managers group with two emailable staff members."""
    group = Group.objects.create(name=INVENTORY_MANAGERS_GROUP)
    liv = User.objects.create_user(
        username='liv', email='liv@example.com', is_staff=True
    )
    linnea = User.objects.create_user(
        username='linnea', email='linnea@example.com', is_staff=True
    )
    liv.groups.add(group)
    linnea.groups.add(group)
    return group, [liv, linnea]


@pytest.fixture
def mock_send_email():
    with patch('apps.account.tasks.email.send_email_by_type.delay') as mocked:
        yield mocked


def alerted_product_names(mock_call):
    """Extract the alerted product names from a send_email_by_type call."""
    return [p['name'] for p in mock_call.kwargs['extra_context']['products']]


# ---------------------------------------------------------------------------
# Alert dispatch
# ---------------------------------------------------------------------------

def test_crossing_threshold_alerts_each_manager_once(
    alert_settings, inventory_managers, mock_send_email
):
    _, managers = inventory_managers
    product = ProductFactory(name='Canned Beans', quantity_in_stock=40)

    check_low_inventory()

    assert mock_send_email.call_count == len(managers)
    alerted_user_ids = {call.args[0] for call in mock_send_email.call_args_list}
    assert alerted_user_ids == {m.pk for m in managers}
    for call in mock_send_email.call_args_list:
        assert call.args[1] == 'low_inventory_alert'
        assert call.kwargs['force'] is True
        assert alerted_product_names(call) == ['Canned Beans']
        assert call.kwargs['extra_context']['threshold'] == 45
        assert call.kwargs['extra_context']['product_count'] == 1

    product.refresh_from_db()
    assert product.low_stock_alerted_at is not None

    # Second run: still low, but already alerted — no new emails.
    mock_send_email.reset_mock()
    check_low_inventory()
    mock_send_email.assert_not_called()


def test_threshold_boundary(alert_settings, inventory_managers, mock_send_email):
    at_threshold = ProductFactory(name='At Threshold', quantity_in_stock=45)
    above_threshold = ProductFactory(name='Above Threshold', quantity_in_stock=46)

    check_low_inventory()

    for call in mock_send_email.call_args_list:
        assert alerted_product_names(call) == ['At Threshold']
    at_threshold.refresh_from_db()
    above_threshold.refresh_from_db()
    assert at_threshold.low_stock_alerted_at is not None
    assert above_threshold.low_stock_alerted_at is None


def test_multiple_low_products_grouped_into_one_email(
    alert_settings, inventory_managers, mock_send_email
):
    _, managers = inventory_managers
    ProductFactory(name='Apples', quantity_in_stock=10)
    ProductFactory(name='Bananas', quantity_in_stock=20)

    check_low_inventory()

    assert mock_send_email.call_count == len(managers)
    for call in mock_send_email.call_args_list:
        assert alerted_product_names(call) == ['Apples', 'Bananas']
        assert call.kwargs['extra_context']['product_count'] == 2


def test_recovery_rearms_even_when_stock_mutated_without_save(
    alert_settings, inventory_managers, mock_send_email
):
    product = ProductFactory(name='Rice', quantity_in_stock=30)
    check_low_inventory()
    assert mock_send_email.call_count == 2
    mock_send_email.reset_mock()

    # Recover via queryset .update() — the same mechanism order
    # cancellation uses, which bypasses save() and signals entirely.
    Product.objects.filter(pk=product.pk).update(quantity_in_stock=100)
    check_low_inventory()
    mock_send_email.assert_not_called()
    product.refresh_from_db()
    assert product.low_stock_alerted_at is None

    # Drop again — a new low episode alerts again.
    Product.objects.filter(pk=product.pk).update(quantity_in_stock=5)
    check_low_inventory()
    assert mock_send_email.call_count == 2


def test_threshold_change_is_respected(
    alert_settings, inventory_managers, mock_send_email
):
    product = ProductFactory(name='Flour', quantity_in_stock=60)

    check_low_inventory()
    mock_send_email.assert_not_called()

    alert_settings.threshold = 100
    alert_settings.save()
    check_low_inventory()
    assert mock_send_email.call_count == 2

    # Lowering the threshold below current stock re-arms the product.
    alert_settings.threshold = 45
    alert_settings.save()
    mock_send_email.reset_mock()
    check_low_inventory()
    mock_send_email.assert_not_called()
    product.refresh_from_db()
    assert product.low_stock_alerted_at is None


# ---------------------------------------------------------------------------
# Suppression rules
# ---------------------------------------------------------------------------

def test_disabled_settings_is_a_noop(
    alert_settings, inventory_managers, mock_send_email
):
    alert_settings.enabled = False
    alert_settings.save()
    product = ProductFactory(quantity_in_stock=1)

    check_low_inventory()

    mock_send_email.assert_not_called()
    product.refresh_from_db()
    assert product.low_stock_alerted_at is None


def test_inactive_product_never_alerts(
    alert_settings, inventory_managers, mock_send_email
):
    ProductFactory(quantity_in_stock=1, active=False)
    check_low_inventory()
    mock_send_email.assert_not_called()


def test_no_emailable_managers_logs_warning(
    alert_settings, mock_send_email, caplog
):
    group = Group.objects.create(name=INVENTORY_MANAGERS_GROUP)
    blank_email = User.objects.create_user(username='no-email', email='')
    inactive = User.objects.create_user(
        username='gone', email='gone@example.com', is_active=False
    )
    blank_email.groups.add(group)
    inactive.groups.add(group)
    product = ProductFactory(quantity_in_stock=10)

    with caplog.at_level(logging.WARNING):
        check_low_inventory()

    mock_send_email.assert_not_called()
    assert any('no emailable members' in record.message for record in caplog.records)
    # The product is still claimed — the episode was observed, delivery
    # simply had nowhere to go.
    product.refresh_from_db()
    assert product.low_stock_alerted_at is not None


def test_missing_group_logs_warning(alert_settings, mock_send_email, caplog):
    ProductFactory(quantity_in_stock=10)

    with caplog.at_level(logging.WARNING):
        check_low_inventory()

    mock_send_email.assert_not_called()
    assert any('no emailable members' in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# Singleton behaviour
# ---------------------------------------------------------------------------

def test_settings_singleton_enforcement(db):
    first = LowInventoryAlertSettings.get_settings()
    assert first.pk == 1
    assert first.threshold == 45
    assert first.enabled is True

    duplicate = LowInventoryAlertSettings(threshold=10, enabled=False)
    duplicate.save()

    assert LowInventoryAlertSettings.objects.count() == 1
    assert duplicate.pk == 1
    refreshed = LowInventoryAlertSettings.get_settings()
    assert refreshed.threshold == 10
    assert refreshed.enabled is False


# ---------------------------------------------------------------------------
# Full pipeline (no mocks)
# ---------------------------------------------------------------------------

def test_full_pipeline_renders_and_logs_email(alert_settings, inventory_managers):
    """Celery is eager in tests, so .delay() sends synchronously.

    Also proves send_email_by_type handles a staff User with no
    Participant (falls back to English rendering).
    """
    email_type, _ = EmailType.objects.get_or_create(
        name='low_inventory_alert',
        defaults=dict(
            display_name='Low Inventory Alert',
            subject='Low inventory alert — {{ product_count }} product(s) at or below {{ threshold }}',
            html_content=(
                '<p>{% for product in products %}{{ product.name }}: '
                '{{ product.quantity_in_stock }} left. {% endfor %}'
                'Threshold: {{ threshold }}</p>'
            ),
            text_content=(
                '{% for product in products %}{{ product.name }}: '
                '{{ product.quantity_in_stock }} left. {% endfor %}'
                'Threshold: {{ threshold }}'
            ),
            is_active=True,
        ),
    )
    ProductFactory(name='Oatmeal', quantity_in_stock=12)

    # User creation above fired onboarding emails — discard those so the
    # outbox only contains what the scan sends.
    mail.outbox.clear()
    check_low_inventory()

    assert len(mail.outbox) == 2
    message = mail.outbox[0]
    assert 'Low inventory alert' in message.subject
    assert 'Oatmeal' in message.body
    assert '12' in message.body
    assert '45' in message.body
    assert EmailLog.objects.filter(
        email_type=email_type, status='sent'
    ).count() == 2


# ---------------------------------------------------------------------------
# Settings API
# ---------------------------------------------------------------------------

class TestLowInventoryAlertSettingsAPI:
    endpoint = '/api/v1/low-inventory-alert-settings/current/'

    def test_staff_can_read_and_update(self, db):
        client = APIClient()
        client.force_authenticate(
            user=User.objects.create_user(
                username='staff', email='staff@example.com', is_staff=True
            )
        )

        response = client.get(self.endpoint)
        assert response.status_code == 200
        assert response.data['threshold'] == 45
        assert response.data['enabled'] is True

        response = client.patch(
            self.endpoint, {'threshold': 30, 'enabled': False}, format='json'
        )
        assert response.status_code == 200
        settings_row = LowInventoryAlertSettings.get_settings()
        assert settings_row.threshold == 30
        assert settings_row.enabled is False

    def test_non_staff_can_read_but_not_write(self, db):
        client = APIClient()
        client.force_authenticate(
            user=User.objects.create_user(
                username='plain', email='plain@example.com'
            )
        )

        assert client.get(self.endpoint).status_code == 200
        response = client.patch(self.endpoint, {'threshold': 5}, format='json')
        assert response.status_code == 403
        assert LowInventoryAlertSettings.get_settings().threshold == 45
