"""
Tests for the password reset API (#137) and the emailed-link redirect.

    POST /api/v1/auth/password-reset/           request a reset email
    POST /api/v1/auth/password-reset/validate/  check a link
    POST /api/v1/auth/password-reset/confirm/   set the new password
    GET  /reset/<uid>/<token>/                  emailed link -> the right app
"""
import pytest
from django.contrib.auth.tokens import default_token_generator
from django.test import Client
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.account.models import UserProfile
from apps.orders.tests.factories import (
    ParticipantFactory,
    UserFactory,
    VoucherSettingFactory,
)

REQUEST_URL = '/api/v1/auth/password-reset/'
VALIDATE_URL = '/api/v1/auth/password-reset/validate/'
CONFIRM_URL = '/api/v1/auth/password-reset/confirm/'
NEW_PASSWORD = 'Harvest-Basket-2026'


@pytest.fixture(autouse=True)
def voucher_setting():
    """ParticipantFactory's balance hook needs an active VoucherSetting."""
    return VoucherSettingFactory(active=True)


@pytest.fixture(autouse=True)
def sent_emails(mocker):
    """The reset email task; also keeps onboarding email off."""
    mocker.patch('apps.account.tasks.email.send_new_user_onboarding_email.delay')
    return mocker.patch(
        'apps.account.api.password_reset_views.send_password_reset_email.delay'
    )


@pytest.fixture
def participant():
    participant = ParticipantFactory()
    participant.user.email = 'pamela@example.com'
    participant.user.save(update_fields=['email'])
    return participant


@pytest.fixture
def staff_user():
    user = UserFactory(username='coordinator', email='staff@example.com', is_staff=True)
    user.save()  # the factory sets the password without saving it
    return user


@pytest.fixture
def api():
    return APIClient()


def link_for(user):
    return {
        'uid': urlsafe_base64_encode(force_bytes(user.pk)),
        'token': default_token_generator.make_token(user),
    }


def request_reset(api, identifier):
    return api.post(REQUEST_URL, {
        'identifier': identifier,
        'recaptcha_token': 'test-token',
    }, format='json')


@pytest.mark.django_db
class TestRequestReset:

    def test_customer_number_sends_to_that_participant(self, api, participant, sent_emails):
        response = request_reset(api, participant.customer_number.lower())

        assert response.status_code == 202
        sent_emails.assert_called_once_with(participant.user.id, force=True)

    def test_email_address_sends_to_that_account(self, api, participant, sent_emails):
        response = request_reset(api, 'PAMELA@example.com')

        assert response.status_code == 202
        sent_emails.assert_called_once_with(participant.user.id, force=True)

    def test_staff_username_sends_to_staff(self, api, staff_user, sent_emails):
        response = request_reset(api, 'Coordinator')

        assert response.status_code == 202
        sent_emails.assert_called_once_with(staff_user.id, force=True)

    def test_unknown_account_gets_the_same_answer(self, api, participant, sent_emails):
        known = request_reset(api, participant.customer_number)
        unknown = request_reset(api, 'C-ZZZ-9')

        assert unknown.status_code == known.status_code == 202
        assert unknown.data == known.data
        assert sent_emails.call_count == 1

    def test_inactive_account_gets_no_email(self, api, participant, sent_emails):
        participant.user.is_active = False
        participant.user.save(update_fields=['is_active'])

        assert request_reset(api, participant.customer_number).status_code == 202
        sent_emails.assert_not_called()

    def test_failed_recaptcha_is_rejected(self, api, participant, sent_emails, mocker):
        mocker.patch(
            'apps.account.api.password_reset_views.verify_recaptcha',
            return_value=(False, 'reCAPTCHA verification failed'),
        )

        response = request_reset(api, participant.customer_number)

        assert response.status_code == 400
        assert response.data['code'] == 'recaptcha_failed'
        sent_emails.assert_not_called()

    def test_blank_identifier_is_400(self, api):
        response = request_reset(api, '  ')

        assert response.status_code == 400
        assert response.data['code'] == 'identifier_required'

    def test_one_identifier_is_rate_limited(self, api, participant, sent_emails):
        for _ in range(5):
            assert request_reset(api, participant.customer_number).status_code == 202

        assert request_reset(api, participant.customer_number).status_code == 429
        # Someone else in the same room can still ask
        assert request_reset(api, 'someone-else').status_code == 202

    def test_a_stale_session_cookie_never_makes_it_401(self, api, participant):
        api.cookies['access_token'] = 'expired-garbage'

        assert request_reset(api, participant.customer_number).status_code == 202


@pytest.mark.django_db
class TestValidateLink:

    def test_valid_link(self, api, participant):
        response = api.post(VALIDATE_URL, link_for(participant.user), format='json')

        assert response.status_code == 200
        assert response.data['valid'] is True

    @pytest.mark.parametrize('link', [
        {'uid': 'bm90LWEtdXNlcg', 'token': 'abc-123'},
        {'uid': '!!!', 'token': 'abc-123'},
        {},
    ])
    def test_bad_links_are_400_not_401(self, api, link):
        response = api.post(VALIDATE_URL, link, format='json')

        assert response.status_code == 400
        assert response.data['code'] == 'invalid_link'

    def test_wrong_token(self, api, participant):
        link = {**link_for(participant.user), 'token': 'not-the-token'}

        assert api.post(VALIDATE_URL, link, format='json').status_code == 400


@pytest.mark.django_db
class TestConfirmReset:

    def test_sets_password_and_returns_how_to_sign_in(self, api, participant):
        UserProfile.objects.update_or_create(
            user=participant.user, defaults={'must_change_password': True})

        response = api.post(CONFIRM_URL, {
            **link_for(participant.user), 'new_password': NEW_PASSWORD,
        }, format='json')

        assert response.status_code == 200
        assert response.data['app'] == 'participant'
        assert response.data['sign_in_as'] == participant.customer_number
        participant.user.refresh_from_db()
        assert participant.user.check_password(NEW_PASSWORD)
        assert UserProfile.objects.get(user=participant.user).must_change_password is False

    def test_staff_signs_in_with_username(self, api, staff_user):
        response = api.post(CONFIRM_URL, {
            **link_for(staff_user), 'new_password': NEW_PASSWORD,
        }, format='json')

        assert response.status_code == 200
        assert response.data == {
            'message': 'Your password is set.',
            'app': 'staff',
            'sign_in_as': 'coordinator',
        }

    def test_link_works_once(self, api, participant):
        link = link_for(participant.user)
        api.post(CONFIRM_URL, {**link, 'new_password': NEW_PASSWORD}, format='json')

        again = api.post(CONFIRM_URL, {**link, 'new_password': 'Another-Basket-2027'},
                         format='json')

        assert again.status_code == 400
        assert again.data['code'] == 'invalid_link'
        participant.user.refresh_from_db()
        assert participant.user.check_password(NEW_PASSWORD)

    def test_weak_password_is_rejected_with_reasons(self, api, participant):
        response = api.post(CONFIRM_URL, {
            **link_for(participant.user), 'new_password': '123',
        }, format='json')

        assert response.status_code == 400
        assert response.data['code'] == 'invalid_password'
        assert response.data['new_password']
        participant.user.refresh_from_db()
        assert not participant.user.check_password('123')

    def test_signs_out_other_sessions(self, api, participant):
        refresh = RefreshToken.for_user(participant.user)

        api.post(CONFIRM_URL, {
            **link_for(participant.user), 'new_password': NEW_PASSWORD,
        }, format='json')

        assert BlacklistedToken.objects.filter(token__jti=refresh['jti']).exists()


@pytest.mark.django_db
class TestEmailedLinkRedirect:

    def test_participant_goes_to_participant_app_in_their_language(self, participant):
        participant.preferred_language = 'es'
        participant.save(update_fields=['preferred_language'])
        link = link_for(participant.user)

        response = Client().get(f"/reset/{link['uid']}/{link['token']}/")

        assert response.status_code == 302
        assert response.url == f"/cart/reset/{link['uid']}/{link['token']}?lang=es"

    def test_staff_goes_to_staff_app(self, staff_user):
        link = link_for(staff_user)

        response = Client().get(f"/reset/{link['uid']}/{link['token']}/")

        assert response.status_code == 302
        assert response.url == f"/new/admin/reset-password/{link['uid']}/{link['token']}"

    def test_undecodable_link_goes_to_participant_app(self):
        response = Client().get('/reset/garbage/abc-123/')

        assert response.status_code == 302
        assert response.url == '/cart/reset/garbage/abc-123'

    @pytest.mark.parametrize('old, new', [
        ('/password_reset/', '/cart/forgot-password'),
        ('/password_reset/done/', '/cart/forgot-password'),
        ('/reset/done/', '/cart/login'),
    ])
    def test_old_reset_pages_go_to_the_app(self, old, new):
        response = Client().get(old)

        assert response.status_code == 302
        assert response.url == new
