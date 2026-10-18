"""
Tests for POST /api/v1/auth/change-password/ and the must_change_password
flag on /api/v1/auth/me/.

Changing a password is voluntary for now: the flag defaults to True and
nothing cleared it before, so it isn't enforced. Changing or resetting a
password clears it.
"""
import pytest
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from apps.account.models import UserProfile
from apps.orders.tests.factories import UserFactory

URL = '/api/v1/auth/change-password/'
NEW_PASSWORD = 'Harvest-Basket-2026'


@pytest.fixture
def user():
    user = UserFactory()
    user.set_password('old-Password-123')
    user.save()
    UserProfile.objects.update_or_create(user=user, defaults={'must_change_password': True})
    return user


@pytest.fixture
def client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def flag(user):
    return UserProfile.objects.get(user=user).must_change_password


@pytest.mark.django_db
class TestChangePassword:

    def test_changes_password_and_clears_flag(self, client, user):
        response = client.post(URL, {
            'current_password': 'old-Password-123',
            'new_password': NEW_PASSWORD,
        }, format='json')

        assert response.status_code == 200
        user.refresh_from_db()
        assert user.check_password(NEW_PASSWORD)
        assert flag(user) is False

    def test_wrong_current_password_is_400_not_401(self, client, user):
        # 401 would make the client think the session expired
        response = client.post(URL, {
            'current_password': 'not-it',
            'new_password': NEW_PASSWORD,
        }, format='json')

        assert response.status_code == 400
        assert response.data['code'] == 'wrong_password'
        assert 'current_password' in response.data
        user.refresh_from_db()
        assert user.check_password('old-Password-123')
        assert flag(user) is True

    def test_weak_new_password_is_rejected_with_reasons(self, client, user):
        response = client.post(URL, {
            'current_password': 'old-Password-123',
            'new_password': '123',
        }, format='json')

        assert response.status_code == 400
        assert response.data['code'] == 'invalid_password'
        assert response.data['new_password']
        user.refresh_from_db()
        assert user.check_password('old-Password-123')

    def test_requires_sign_in(self):
        response = APIClient().post(URL, {
            'current_password': 'x', 'new_password': NEW_PASSWORD,
        }, format='json')

        assert response.status_code == 401

    def test_works_without_a_profile(self, client, user):
        UserProfile.objects.filter(user=user).delete()

        response = client.post(URL, {
            'current_password': 'old-Password-123',
            'new_password': NEW_PASSWORD,
        }, format='json')

        assert response.status_code == 200


@pytest.mark.django_db
class TestAuthMeFlag:

    def test_reports_flag(self, client, user):
        assert client.get('/api/v1/auth/me/').data['user']['must_change_password'] is True

        UserProfile.objects.filter(user=user).update(must_change_password=False)

        assert client.get('/api/v1/auth/me/').data['user']['must_change_password'] is False

    def test_false_without_a_profile(self, client, user):
        UserProfile.objects.filter(user=user).delete()

        assert client.get('/api/v1/auth/me/').data['user']['must_change_password'] is False


@pytest.mark.django_db
def test_django_password_reset_clears_flag(client, user):
    """The emailed reset link still uses Django's page; it clears the flag too."""
    from django.test import Client

    browser = Client()
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    # Django swaps the token for a session marker on the first visit
    response = browser.get(f'/reset/{uid}/{token}/')
    assert response.status_code == 302
    response = browser.post(response.url, {
        'new_password1': NEW_PASSWORD,
        'new_password2': NEW_PASSWORD,
    })

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)
    assert flag(user) is False
