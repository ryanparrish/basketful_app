"""
Tests that participant-facing API errors honor the participant's
preferred_language, while machine-readable fields stay stable.

Requires compiled Spanish catalogs (python manage.py compilemessages -l es);
CI compiles them before pytest runs.
"""
import pytest
from django.utils import translation
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.orders.tests.factories import (
    OrderFactory,
    ParticipantFactory,
    ProductFactory,
    VoucherSettingFactory,
)


@pytest.fixture(autouse=True)
def voucher_setting():
    return VoucherSettingFactory(active=True)


@pytest.fixture(autouse=True)
def reset_language():
    yield
    translation.activate('en')


def jwt_client_for(user):
    """Real JWT auth (not force_authenticate) so the language-activation
    hook in CookieJWTAuthentication actually runs."""
    client = APIClient()
    token = AccessToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


@pytest.mark.django_db
class TestOrderErrorLanguage:
    """Order-creation errors arrive in the participant's language."""

    def _create_order_payload(self, participant, product):
        return {
            'account': participant.accountbalance.id,
            'items': [{'product': product.id, 'quantity': 1}],
        }

    def test_spanish_participant_gets_spanish_duplicate_order_error(self):
        participant = ParticipantFactory(preferred_language='es')
        OrderFactory(account=participant.accountbalance, status='pending')
        product = ProductFactory(price=1)

        client = jwt_client_for(participant.user)
        response = client.post(
            '/api/v1/orders/',
            self._create_order_payload(participant, product),
            format='json',
        )

        assert response.status_code == 400, response.data
        assert 'Ya tiene un pedido activo' in str(response.data)

    def test_english_participant_gets_english_duplicate_order_error(self):
        participant = ParticipantFactory(preferred_language='en')
        OrderFactory(account=participant.accountbalance, status='pending')
        product = ProductFactory(price=1)

        client = jwt_client_for(participant.user)
        response = client.post(
            '/api/v1/orders/',
            self._create_order_payload(participant, product),
            format='json',
        )

        assert response.status_code == 400, response.data
        assert 'You already have an active order' in str(response.data)


@pytest.mark.django_db
class TestValidateCartLanguage:
    """validate-cart messages translate; the `type` contract does not."""

    def _over_balance_cart(self, participant):
        expensive_product = ProductFactory(price=100000)
        return {'items': [{'product_id': expensive_product.id, 'quantity': 5}]}

    def test_spanish_messages_with_stable_types(self):
        participant = ParticipantFactory(preferred_language='es')
        client = jwt_client_for(participant.user)

        response = client.post(
            '/api/v1/orders/validate-cart/',
            self._over_balance_cart(participant),
            format='json',
        )

        assert response.status_code == 200, response.data
        violations = response.data['violations']
        assert violations, 'expected an over-balance violation'
        balance_violations = [v for v in violations if v['type'] == 'balance']
        assert balance_violations, 'type must remain the untranslated machine key'
        assert any(
            'se excedió' in v['message'] for v in balance_violations
        ), balance_violations

    def test_english_messages_by_default(self):
        participant = ParticipantFactory(preferred_language='en')
        client = jwt_client_for(participant.user)

        response = client.post(
            '/api/v1/orders/validate-cart/',
            self._over_balance_cart(participant),
            format='json',
        )

        assert response.status_code == 200, response.data
        balance_violations = [
            v for v in response.data['violations'] if v['type'] == 'balance'
        ]
        assert any(
            'balance exceeded by' in v['message'] for v in balance_violations
        ), balance_violations


@pytest.mark.django_db
class TestStaffStaysEnglish:
    """Staff API responses are pinned to English regardless of headers."""

    def test_staff_request_with_spanish_accept_language_stays_english(self):
        from apps.orders.tests.factories import UserFactory
        staff_user = UserFactory(is_staff=True)
        client = jwt_client_for(staff_user)
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(staff_user)}',
            HTTP_ACCEPT_LANGUAGE='es',
        )

        response = client.post(
            '/api/v1/orders/validate-cart/',
            {'items': []},
            format='json',
        )

        # Staff user has no participant profile → English 404 message
        assert response.status_code == 404, response.data
        assert 'No participant profile found' in str(response.data['error'])
