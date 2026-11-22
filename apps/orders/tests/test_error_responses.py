"""Order API error responses carry readable messages, not exception reprs (#149)."""
from unittest import mock

import pytest
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.orders.models import Order
from apps.orders.tests.factories import (
    ParticipantFactory,
    ProgramFactory,
    UserFactory,
    VoucherSettingFactory,
)

COMBINED_PREVIEW_URL = '/api/v1/combined-orders/preview/'


@pytest.fixture
def singletons(db):
    from core.models import ProgramSettings

    VoucherSettingFactory.create()
    ProgramSettings.get_settings()


@pytest.fixture
def staff_client():
    client = APIClient()
    client.force_authenticate(user=UserFactory(is_staff=True, is_superuser=True))
    return client


@pytest.mark.django_db
def test_cancel_validation_error_returns_plain_message(singletons, staff_client):
    participant = ParticipantFactory()
    order = Order(account=participant.accountbalance, status='pending')
    order.save()

    with mock.patch(
        'apps.orders.models.Order.save',
        side_effect=ValidationError('Order is locked for packing.'),
    ):
        response = staff_client.post(f'/api/v1/orders/{order.id}/cancel/', {}, format='json')

    assert response.status_code == 400
    assert response.data['error'] == 'Order is locked for packing.'


@pytest.mark.django_db
def test_combined_preview_unknown_program_is_404_without_exception_text(staff_client):
    response = staff_client.post(
        COMBINED_PREVIEW_URL,
        {'program_id': 999999, 'start_date': '2026-11-01', 'end_date': '2026-11-07'},
        format='json',
    )

    assert response.status_code == 404
    assert response.data['error'] == 'Program not found.'


@pytest.mark.django_db
def test_combined_preview_bad_date_does_not_echo_parser_error(staff_client):
    program = ProgramFactory()
    response = staff_client.post(
        COMBINED_PREVIEW_URL,
        {'program_id': program.id, 'start_date': 'not-a-date', 'end_date': '2026-11-07'},
        format='json',
    )

    assert response.status_code == 400
    assert 'isoformat' not in response.data['error']
    assert 'YYYY-MM-DD' in response.data['error']
