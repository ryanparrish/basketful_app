"""
Regression test: GET /api/v1/orders/?participant=<id> returns only that
participant's orders.

Before the `participant` filter existed on OrderFilter, django-filter
silently ignored the param and the admin participant page's Orders tab
showed every order in the system.
"""
import pytest
from rest_framework.test import APIClient

from apps.orders.tests.factories import (
    OrderFactory,
    ParticipantFactory,
    UserFactory,
    VoucherSettingFactory,
)


@pytest.fixture(autouse=True)
def voucher_setting():
    return VoucherSettingFactory(active=True)


@pytest.fixture
def staff_client():
    client = APIClient()
    client.force_authenticate(user=UserFactory(is_staff=True))
    return client


@pytest.mark.django_db
class TestOrderParticipantFilter:

    def test_filters_to_single_participants_orders(self, staff_client):
        alicia = ParticipantFactory()
        other = ParticipantFactory()
        alicia_orders = [
            OrderFactory(account=alicia.accountbalance, status='completed')
            for _ in range(2)
        ]
        OrderFactory(account=other.accountbalance, status='completed')

        response = staff_client.get(f'/api/v1/orders/?participant={alicia.id}')

        assert response.status_code == 200, response.data
        results = response.data.get('results', response.data)
        returned_ids = {order['id'] for order in results}
        assert returned_ids == {order.id for order in alicia_orders}

    def test_unfiltered_list_still_returns_all_orders(self, staff_client):
        first = ParticipantFactory()
        second = ParticipantFactory()
        OrderFactory(account=first.accountbalance, status='completed')
        OrderFactory(account=second.accountbalance, status='completed')

        response = staff_client.get('/api/v1/orders/')

        assert response.status_code == 200
        results = response.data.get('results', response.data)
        assert len(results) == 2
