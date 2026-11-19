"""
Issue #136: a failed API sign-in must return the serializer's real error and
write a UserLoginLog row.

CookieTokenObtainView built its serializer without the request, so
authenticate() fired user_login_failed with request=None. The logger then
crashed on request.META, no row was written, and the view returned
"'NoneType' object has no attribute 'META'" as the 401 detail.
"""
import pytest
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.log.models import UserLoginLog

LOGIN = "/api/v1/auth/login/"
CLIENT_IP = "198.51.100.23"
BROWSER = "Mozilla/5.0 (test browser)"


@pytest.fixture(autouse=True)
def _fresh_cache(settings):
    settings.RECAPTCHA_PRIVATE_KEY = "test-private-key"
    cache.clear()
    yield
    cache.clear()


def post_login(username, password):
    return APIClient().post(
        LOGIN,
        {"username": username, "password": password, "recaptcha_token": "t"},
        format="json",
        REMOTE_ADDR=CLIENT_IP,
        HTTP_USER_AGENT=BROWSER,
    )


@pytest.mark.django_db
def test_wrong_password_returns_real_error_and_logs_the_attempt():
    User.objects.create_user(username="PamelaDan-test", password="right-pass")

    response = post_login("PamelaDan-test", "wrong-pass")

    assert response.status_code == 401, response.data
    assert response.data["code"] == "invalid_password", response.data
    assert "META" not in str(response.data)

    failed_attempt = UserLoginLog.objects.get(action=UserLoginLog.FAILED_LOGIN)
    assert failed_attempt.username_attempted == "PamelaDan-test"
    assert failed_attempt.ip_address == CLIENT_IP
    assert failed_attempt.user_agent == BROWSER


@pytest.mark.django_db
def test_correct_password_still_signs_in():
    User.objects.create_user(username="PamelaDan-test", password="right-pass")

    response = post_login("PamelaDan-test", "right-pass")

    assert response.status_code == 200, response.data
    assert not UserLoginLog.objects.filter(action=UserLoginLog.FAILED_LOGIN).exists()


@pytest.mark.django_db
def test_failed_login_without_a_request_is_still_logged():
    """Any caller may authenticate() without a request; the logger must cope."""
    User.objects.create_user(username="no-request-user", password="right-pass")

    assert authenticate(request=None, username="no-request-user", password="nope") is None

    failed_attempt = UserLoginLog.objects.get(action=UserLoginLog.FAILED_LOGIN)
    assert failed_attempt.username_attempted == "no-request-user"
    assert failed_attempt.ip_address is None
    assert failed_attempt.user_agent == ""
