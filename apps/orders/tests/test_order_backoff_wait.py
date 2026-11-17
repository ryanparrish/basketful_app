"""
Issue #119: the 429 for an order submission rejected by failure backoff must
report the real backoff remaining, not a wait derived from the rate window.

Policy (kept deliberately): a failed Place Order attempt, including a
correctable validation failure, still starts the exponential backoff
(2s, doubling, capped at 60s). Only the reported wait was wrong: a 2-second
backoff answered "Expected available in 30 seconds" with Retry-After: 30.
"""
import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.orders.api.throttles import increment_failure_count, reset_failure_count
from apps.orders.tests.factories import (
    ParticipantFactory,
    ProductFactory,
    VoucherSettingFactory,
)
from apps.orders.tests.helpers import no_order_window

ORDERS_URL = '/api/v1/orders/'


@pytest.fixture(autouse=True)
def voucher_setting():
    return VoucherSettingFactory(active=True)


@pytest.fixture(autouse=True)
def clear_throttle_state():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def participant_client():
    participant = ParticipantFactory()
    no_order_window(participant.program)
    client = APIClient()
    client.force_authenticate(user=participant.user)
    return participant, client


def _post_order(client, product, quantity=1):
    return client.post(
        ORDERS_URL,
        {'items': [{'product': product.id, 'quantity': quantity}]},
        format='json',
    )


@pytest.mark.django_db
def test_retry_after_correctable_failure_reports_real_backoff(participant_client):
    """Over-balance 400, then an immediate retry gets a 429 quoting ~2s, not 30s."""
    _, client = participant_client
    unaffordable_product = ProductFactory(price=100000)

    first_attempt = _post_order(client, unaffordable_product)
    assert first_attempt.status_code == 400, first_attempt.data

    retry = _post_order(client, unaffordable_product)

    assert retry.status_code == 429, retry.data
    assert int(retry['Retry-After']) <= 2
    assert '30 seconds' not in str(retry.data['detail'])


@pytest.mark.django_db
def test_retry_after_matches_backoff_after_repeated_failures(participant_client):
    """Third failure in the hour is an 8s backoff, and the 429 says so."""
    participant, client = participant_client
    for _ in range(3):
        backoff_seconds = increment_failure_count(participant.user.id)
    assert backoff_seconds == 8

    response = _post_order(client, ProductFactory(price=1))

    assert response.status_code == 429, response.data
    retry_after = int(response['Retry-After'])
    assert retry_after in (7, 8)
    assert f'Expected available in {retry_after} seconds' in str(response.data['detail'])


@pytest.mark.django_db
def test_backoff_rejections_do_not_use_up_the_per_minute_limit(participant_client):
    """
    Retries refused by backoff must not count toward the 3/minute rate, or a
    participant who retried during a short backoff would then be locked out
    for the rest of the minute.
    """
    participant, client = participant_client
    affordable_product = ProductFactory(price=1)

    increment_failure_count(participant.user.id)
    for _ in range(3):
        assert _post_order(client, affordable_product).status_code == 429

    reset_failure_count(participant.user.id)
    response = _post_order(client, affordable_product)

    assert response.status_code == 201, response.data
