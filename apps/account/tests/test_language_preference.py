"""
Tests for participant language preference plumbing.

Covers the bilingual foundation:
- GET /api/v1/participants/me/profile/ returns preferred_language
- PATCH /api/v1/participants/me/profile/ updates only preferred_language
- Invalid language codes are rejected
- The PATCH does not trigger household-change side effects (balance recalc)
- CookieJWTAuthentication activates the participant's language and pins
  staff to English
- The login payload includes preferred_language
"""
import pytest
from django.utils import translation
from rest_framework.test import APIClient

from apps.account.api.authentication import CookieJWTAuthentication
from apps.account.models import AccountBalance
from apps.orders.tests.factories import (
    ParticipantFactory,
    UserFactory,
    VoucherSettingFactory,
)


@pytest.fixture(autouse=True)
def voucher_setting():
    """Active VoucherSetting is required by ParticipantFactory's balance hook."""
    return VoucherSettingFactory(active=True)


@pytest.fixture(autouse=True)
def reset_language():
    """Keep translation.activate() calls from leaking between tests."""
    yield
    translation.activate('en')


@pytest.fixture
def participant():
    return ParticipantFactory()


@pytest.fixture
def participant_client(participant):
    client = APIClient()
    client.force_authenticate(user=participant.user)
    return client


@pytest.mark.django_db
class TestPreferredLanguageEndpoint:
    """GET/PATCH /api/v1/participants/me/profile/ preferred_language handling."""

    def test_get_profile_returns_preferred_language(self, participant_client):
        response = participant_client.get('/api/v1/participants/me/profile/')

        assert response.status_code == 200, response.data
        assert response.data['preferred_language'] == 'en'

    def test_patch_persists_preferred_language(self, participant, participant_client):
        response = participant_client.patch(
            '/api/v1/participants/me/profile/',
            {'preferred_language': 'es'},
            format='json',
        )

        assert response.status_code == 200, response.data
        assert response.data['preferred_language'] == 'es'
        participant.refresh_from_db()
        assert participant.preferred_language == 'es'

    def test_patch_rejects_unknown_language(self, participant, participant_client):
        response = participant_client.patch(
            '/api/v1/participants/me/profile/',
            {'preferred_language': 'fr'},
            format='json',
        )

        assert response.status_code == 400
        participant.refresh_from_db()
        assert participant.preferred_language == 'en'

    def test_patch_ignores_other_fields(self, participant, participant_client):
        """Only preferred_language may change through this endpoint."""
        original_name = participant.name

        response = participant_client.patch(
            '/api/v1/participants/me/profile/',
            {'preferred_language': 'es', 'name': 'Hijacked Name', 'adults': 99},
            format='json',
        )

        assert response.status_code == 200, response.data
        participant.refresh_from_db()
        assert participant.name == original_name
        assert participant.adults != 99
        assert participant.preferred_language == 'es'

    def test_patch_does_not_recalculate_balance(self, participant, participant_client):
        """update_fields must keep household signal handlers from firing."""
        account = AccountBalance.objects.get(participant=participant)
        original_base_balance = account.base_balance

        response = participant_client.patch(
            '/api/v1/participants/me/profile/',
            {'preferred_language': 'es'},
            format='json',
        )

        assert response.status_code == 200, response.data
        account.refresh_from_db()
        assert account.base_balance == original_base_balance

    def test_anonymous_request_is_rejected(self):
        client = APIClient()
        response = client.patch(
            '/api/v1/participants/me/profile/',
            {'preferred_language': 'es'},
            format='json',
        )
        assert response.status_code in (401, 403)


@pytest.mark.django_db
class TestLanguageActivation:
    """CookieJWTAuthentication activates the right language per user."""

    def test_participant_language_is_activated(self):
        participant = ParticipantFactory(preferred_language='es')

        CookieJWTAuthentication._activate_user_language(participant.user)

        assert translation.get_language() == 'es'

    def test_staff_is_pinned_to_english(self):
        staff_user = UserFactory(is_staff=True)
        translation.activate('es')

        CookieJWTAuthentication._activate_user_language(staff_user)

        assert translation.get_language() == 'en'

    def test_user_without_participant_keeps_request_language(self):
        user = UserFactory()
        translation.activate('en')

        CookieJWTAuthentication._activate_user_language(user)

        assert translation.get_language() == 'en'


@pytest.mark.django_db
class TestLoginPayloadLanguage:
    """POST /api/v1/token/ returns the participant's preferred_language."""

    def test_login_response_includes_preferred_language(self):
        participant = ParticipantFactory(preferred_language='es')
        # skip_postgeneration_save on the factory means the hashed password
        # from UserFactory's post-generation hook is never persisted.
        participant.user.set_password('password123')
        participant.user.save(update_fields=['password'])

        client = APIClient()
        response = client.post(
            '/api/v1/token/',
            {'username': participant.user.username, 'password': 'password123'},
            format='json',
        )

        assert response.status_code == 200, response.data
        assert response.data['user']['preferred_language'] == 'es'
