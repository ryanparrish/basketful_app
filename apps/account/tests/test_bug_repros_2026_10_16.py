"""Reproduction test for confirmed Basketful bug H5 (2026-10-16 review).

The test asserts the CORRECT behavior and FAILS on the current code,
demonstrating the bug. Do NOT "fix" this test to pass — fix the code.

Covers: H5, H6 (+ more as the fix pass proceeds).

Environment: run on SQLite via the test-only settings shim:
    DATABASE_URL="sqlite:////tmp/test_db.sqlite3" SECRET_KEY=x HASHIDS_SALT=y \
    DJANGO_SETTINGS_MODULE=apps.orders.tests.repro_sqlite_settings \
    python -m pytest apps/account/tests/test_bug_repros_2026_10_16.py
"""

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from apps.account.api.jwt_serializers import FlexibleTokenObtainPairSerializer


@pytest.mark.django_db
def test_h5_username_starting_with_c_authenticates_as_username():
    """H5 — usernames starting with "C" can't log in.

    apps/account/api/jwt_serializers.py:28-45 —
    `identifier.upper().startswith('C') and len(identifier) >= 5` routes the
    identifier to the customer-number branch. A generated username like
    "Christina-anchor" (format {Name}-{noun}) is forced through the C-XXX-D
    check-digit validation, which fails -> 401 invalid_customer_number_format.

    Expected: the username branch authenticates the user and returns tokens.
    Actual (current code): AuthenticationFailed(invalid_customer_number_format)
    -> test FAILS, demonstrating H5.
    """
    User.objects.create_user(username="Christina-anchor", password="s3cret-pass")

    serializer = FlexibleTokenObtainPairSerializer()
    try:
        data = serializer.validate(
            {"username": "Christina-anchor", "password": "s3cret-pass"}
        )
    except AuthenticationFailed as exc:
        detail = exc.detail
        code = detail.get("code") if isinstance(detail, dict) else detail
        pytest.fail(
            "username 'Christina-anchor' was routed to customer-number "
            f"validation and rejected (code={code}); it should authenticate "
            "as a username login"
        )

    assert "access" in data and "refresh" in data


@pytest.mark.django_db
def test_h6_logout_works_with_expired_access_token():
    """H6 — logout silently fails when the access token has expired.

    apps/account/api/auth_views.py (CookieTokenLogoutView) —
    permission_classes = [IsAuthenticated] rejects the request before the
    body runs when the 60-min access cookie has lapsed, so the refresh cookie
    is never blacklisted or cleared. On a shared/family computer the 7-day
    refresh cookie survives and the next visitor is silently logged in as the
    previous participant.

    Expected: POST /api/v1/auth/logout/ with no (expired) access cookie but
    a valid refresh cookie returns 200, blacklists the refresh token, and
    clears both cookies.
    Actual (current code): 401, refresh token still usable -> test FAILS,
    demonstrating H6.
    """
    from django.conf import settings
    from rest_framework_simplejwt.tokens import RefreshToken
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

    user = User.objects.create_user(username="h6user", password="s3cret-pass")
    refresh = RefreshToken.for_user(user)
    refresh_cookie = settings.SIMPLE_JWT.get("AUTH_COOKIE_REFRESH", "refresh_token")
    access_cookie = settings.SIMPLE_JWT.get("AUTH_COOKIE", "access_token")

    client = APIClient()
    # No access cookie: exactly what a browser sends after the 60-min access
    # token lapsed. Only the refresh cookie is present.
    client.cookies[refresh_cookie] = str(refresh)

    resp = client.post("/api/v1/auth/logout/")

    assert resp.status_code == 200, (
        "logout must work with an expired access token; "
        f"got {resp.status_code}: {getattr(resp, 'data', None)}"
    )
    # The refresh token must be dead after logout...
    assert BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists(), (
        "refresh token was not blacklisted by logout"
    )
    # ...and both cookies cleared.
    for name in (access_cookie, refresh_cookie):
        morsel = resp.cookies.get(name)
        assert morsel is not None and str(morsel["max-age"]) == "0", (
            f"expected {name} cookie to be cleared, got {morsel.output(header='') if morsel else None}"
        )


@pytest.mark.django_db
def test_h7_retried_refresh_after_rotation_gets_new_tokens():
    """H7 — refresh-token rotation with no reuse grace kills sessions.

    apps/account/api/auth_views.py (CookieTokenRefreshView) —
    ROTATE_REFRESH_TOKENS=True + BLACKLIST_AFTER_ROTATION=True. Two tabs
    refreshing at the same access-token expiry, or a refresh retried after a
    network blip (server rotated, client never got the new cookies) → the
    second presentation of the old token 401s with the misleading "Session
    expired. Please sign in again."

    Expected: presenting the just-rotated refresh token within a short reuse
    grace window returns 200 with fresh tokens instead of 401.
    Actual (current code): 401 token_expired -> test FAILS, demonstrating H7.
    """
    from django.conf import settings
    from rest_framework_simplejwt.tokens import RefreshToken

    user = User.objects.create_user(username="h7user", password="s3cret-pass")
    refresh = RefreshToken.for_user(user)
    refresh_cookie = settings.SIMPLE_JWT.get("AUTH_COOKIE_REFRESH", "refresh_token")

    client = APIClient()
    client.cookies[refresh_cookie] = str(refresh)

    # First refresh: server rotates R1 -> R2 and blacklists R1.
    resp1 = client.post("/api/v1/auth/refresh/")
    assert resp1.status_code == 200, f"first refresh failed: {getattr(resp1, 'data', None)}"

    # The client never received R2 (network blip / second tab): it retries
    # with the now-blacklisted R1.
    client.cookies[refresh_cookie] = str(refresh)
    resp2 = client.post("/api/v1/auth/refresh/")

    assert resp2.status_code == 200, (
        "retried refresh within the reuse grace window should return fresh "
        f"tokens, got {resp2.status_code}: {getattr(resp2, 'data', None)}"
    )


@pytest.mark.django_db
def test_h8_reset_password_actually_sends_email(mocker):
    """H8 — reset_password is a stub that reports success without sending.

    apps/account/api/views.py (UserViewSet.reset_password) — returns
    {'status': 'password reset email sent'} while the
    '# TODO: Implement password reset email' was never done. Staff tell a
    locked-out participant to check their inbox; nothing ever arrives.

    Expected: POST /api/v1/users/{id}/reset_password/ enqueues the
    password-reset email task for that user.
    Actual (current code): 200 with no dispatch -> test FAILS,
    demonstrating H8.
    """
    from apps.orders.tests.factories import UserFactory as OrdersUserFactory

    staff = OrdersUserFactory(is_staff=True)
    target = OrdersUserFactory()
    client = APIClient()
    client.force_authenticate(user=staff)

    mock_delay = mocker.patch(
        "apps.account.api.views.send_password_reset_email.delay"
    )
    resp = client.post(
        f"/api/v1/users/{target.id}/reset_password/", {}, format="json"
    )

    assert resp.status_code == 200, f"reset_password failed: {getattr(resp, 'data', None)}"
    mock_delay.assert_called_once_with(target.id, force=True)
