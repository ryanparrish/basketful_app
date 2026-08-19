"""
Regression test: a participant's own orders must be visible under
GET /api/v1/orders/?me=true and GET /api/v1/orders/<id>/, even though
Order.user (a separate, frequently-null "who submitted this" audit
field) was never set on the order.

Order.user is left unset by OrderFactory, the legacy session-cart view
(apps/orders/views.py), seed_test_orders, and OrderOrchestration.create_order
itself — so "my orders" must be scoped through the real ownership chain
(account -> participant -> user), not through Order.user.
"""
import pytest
from rest_framework.test import APIClient

from apps.orders.tests.factories import (
    OrderFactory,
    ParticipantFactory,
    VoucherSettingFactory,
)


@pytest.fixture(autouse=True)
def voucher_setting():
    return VoucherSettingFactory(active=True)


@pytest.mark.django_db
class TestOrderOwnershipScoping:

    def test_me_true_returns_order_with_unset_user_field(self):
        participant = ParticipantFactory()
        order = OrderFactory(account=participant.accountbalance, status='completed')
        assert order.user is None

        client = APIClient()
        client.force_authenticate(user=participant.user)

        response = client.get('/api/v1/orders/?me=true')

        assert response.status_code == 200, response.data
        results = response.data.get('results', response.data)
        assert {o['id'] for o in results} == {order.id}

    def test_me_true_does_not_leak_other_participants_orders(self):
        participant = ParticipantFactory()
        other = ParticipantFactory()
        OrderFactory(account=other.accountbalance, status='completed')

        client = APIClient()
        client.force_authenticate(user=participant.user)

        response = client.get('/api/v1/orders/?me=true')

        assert response.status_code == 200, response.data
        results = response.data.get('results', response.data)
        assert results == []

    def test_participant_can_retrieve_own_order_detail(self):
        participant = ParticipantFactory()
        order = OrderFactory(account=participant.accountbalance, status='completed')
        assert order.user is None

        client = APIClient()
        client.force_authenticate(user=participant.user)

        response = client.get(f'/api/v1/orders/{order.id}/')

        assert response.status_code == 200, response.data

    def test_participant_cannot_retrieve_another_participants_order(self):
        participant = ParticipantFactory()
        other = ParticipantFactory()
        other_order = OrderFactory(account=other.accountbalance, status='completed')

        client = APIClient()
        client.force_authenticate(user=participant.user)

        response = client.get(f'/api/v1/orders/{other_order.id}/')

        assert response.status_code == 404, response.data
