"""
Regression test: POST /api/v1/orders/ must succeed when `account` is
omitted from the payload — this is the shape the participant frontend
actually sends (it has no way to know its own AccountBalance ID), unlike
every other order-creation test in this suite, which explicitly includes
`account` and so never caught that self-service checkout was broken.

Staff omitting `account` must still be rejected, since staff act on
behalf of other participants and the server cannot guess which one.
"""
import pytest
from rest_framework.test import APIClient

from apps.orders.tests.factories import (
    ParticipantFactory,
    ProductFactory,
    UserFactory,
    VoucherSettingFactory,
)


@pytest.fixture(autouse=True)
def voucher_setting():
    return VoucherSettingFactory(active=True)


@pytest.mark.django_db
class TestOrderCreateOmitsAccount:

    def test_participant_checkout_without_account_field_succeeds(self):
        participant = ParticipantFactory()
        product = ProductFactory(price=1)
        client = APIClient()
        client.force_authenticate(user=participant.user)

        response = client.post(
            '/api/v1/orders/',
            {'items': [{'product': product.id, 'quantity': 1}]},
            format='json',
        )

        assert response.status_code == 201, response.data
        assert response.data['account'] == participant.accountbalance.id

    def test_participant_without_a_participant_profile_is_rejected(self):
        user = UserFactory(is_staff=False)
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(
            '/api/v1/orders/',
            {'items': []},
            format='json',
        )

        assert response.status_code == 400, response.data
        assert 'account' in response.data

    def test_staff_omitting_account_is_rejected(self):
        staff_user = UserFactory(is_staff=True)
        client = APIClient()
        client.force_authenticate(user=staff_user)

        response = client.post(
            '/api/v1/orders/',
            {'items': []},
            format='json',
        )

        assert response.status_code == 400, response.data
        assert 'account' in response.data
