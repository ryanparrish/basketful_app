"""Sign-in and session fixes for participants at program sites.

#112: usernames starting with C were sent to customer-number validation.
#113: a refresh token presented again just after rotation forced a logout.
#114: logins and refreshes from one address shared five tries a minute.
"""
import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken

from apps.account.api.jwt_serializers import FlexibleTokenObtainPairSerializer

LOGIN = "/api/v1/auth/login/"
REFRESH = "/api/v1/auth/refresh/"
LOGOUT = "/api/v1/auth/logout/"
SITE = "198.51.100.7"
REFRESH_COOKIE = settings.SIMPLE_JWT.get("AUTH_COOKIE_REFRESH", "refresh_token")


@pytest.fixture(autouse=True)
def _fresh_cache(settings):
    settings.RECAPTCHA_PRIVATE_KEY = "test-private-key"
    cache.clear()
    yield
    cache.clear()


def login(client, username, password):
    return client.post(
        LOGIN,
        {"username": username, "password": password, "recaptcha_token": "t"},
        format="json",
        REMOTE_ADDR=SITE,
    )


def client_with_refresh(token):
    client = APIClient()
    client.cookies[REFRESH_COOKIE] = str(token)
    return client


# --- #112 -------------------------------------------------------------------

@pytest.mark.django_db
def test_username_starting_with_c_signs_in():
    User.objects.create_user(username="Christina-anchor", password="s3cret-pass")
    data = FlexibleTokenObtainPairSerializer().validate(
        {"username": "Christina-anchor", "password": "s3cret-pass"}
    )
    assert "access" in data and "refresh" in data


@pytest.mark.django_db
def test_unknown_customer_number_still_checked_as_one():
    with pytest.raises(AuthenticationFailed) as exc:
        FlexibleTokenObtainPairSerializer().validate(
            {"username": "Cxyz-nope", "password": "x"}
        )
    assert exc.value.detail["code"] == "invalid_customer_number_format"


@pytest.mark.django_db
def test_unknown_username_is_username_not_found():
    with pytest.raises(AuthenticationFailed) as exc:
        FlexibleTokenObtainPairSerializer().validate(
            {"username": "nobody", "password": "x"}
        )
    assert exc.value.detail["code"] == "username_not_found"


# --- #113 -------------------------------------------------------------------

@pytest.mark.django_db
def test_retried_refresh_after_rotation_gets_the_same_tokens():
    user = User.objects.create_user(username="p1", password="pw-12345")
    r1 = RefreshToken.for_user(user)
    client = client_with_refresh(r1)

    first = client.post(REFRESH)
    assert first.status_code == 200
    # Copy now: the test client shares these cookie objects with its jar.
    names = (REFRESH_COOKIE, settings.SIMPLE_JWT.get("AUTH_COOKIE", "access_token"))
    issued = {name: first.cookies[name].value for name in names}

    # The new cookies never arrived (second tab, network blip): retry with R1.
    client.cookies[REFRESH_COOKIE] = str(r1)
    retry = client.post(REFRESH)
    assert retry.status_code == 200, retry.data
    assert {name: retry.cookies[name].value for name in names} == issued


@pytest.mark.django_db
def test_logged_out_refresh_token_gets_no_grace():
    user = User.objects.create_user(username="p1", password="pw-12345")
    token = RefreshToken.for_user(user)
    client = client_with_refresh(token)
    client.force_authenticate(user)
    assert client.post(LOGOUT).status_code == 200

    client.force_authenticate(None)
    client.cookies[REFRESH_COOKIE] = str(token)
    resp = client.post(REFRESH)
    assert resp.status_code == 401
    assert resp.data["code"] == "token_expired"


@pytest.mark.django_db
def test_grace_ends_when_the_user_is_deactivated():
    user = User.objects.create_user(username="p1", password="pw-12345")
    r1 = RefreshToken.for_user(user)
    client = client_with_refresh(r1)
    assert client.post(REFRESH).status_code == 200

    User.objects.filter(pk=user.pk).update(is_active=False)
    client.cookies[REFRESH_COOKIE] = str(r1)
    assert client.post(REFRESH).status_code == 401


# --- #114 -------------------------------------------------------------------

@pytest.mark.django_db
def test_refresh_not_starved_by_logins_from_same_address():
    User.objects.create_user(username="p1", password="pw-12345")
    for _ in range(6):
        login(APIClient(), "p1", "pw-12345")

    other = User.objects.create_user(username="p2", password="pw-12345")
    resp = client_with_refresh(RefreshToken.for_user(other)).post(REFRESH, REMOTE_ADDR=SITE)
    assert resp.status_code == 200, resp.data


@pytest.mark.django_db
def test_a_room_can_sign_in_together():
    for i in range(12):
        User.objects.create_user(username=f"p{i}", password="pw-12345")
    codes = [login(APIClient(), f"p{i}", "pw-12345").status_code for i in range(12)]
    assert codes == [200] * 12


@pytest.mark.django_db
def test_guessing_one_username_is_still_limited():
    User.objects.create_user(username="victim", password="right-pass")
    codes = [login(APIClient(), "Victim", f"guess-{i}").status_code for i in range(6)]
    assert codes[:5] == [401] * 5
    assert codes[5] == 429


@pytest.mark.django_db
def test_one_address_is_capped_across_usernames():
    codes = [login(APIClient(), f"user{i}", "x").status_code for i in range(31)]
    assert 429 not in codes[:30]
    assert codes[30] == 429
