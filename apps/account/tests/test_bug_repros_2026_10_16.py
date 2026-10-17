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


@pytest.mark.django_db
def test_m11_forced_password_change_end_to_end():
    """M11 — must_change_password enforcement is dead in three ways.

    (1) apps/pantry/middleware.py reads the flag off request.user, but it
    lives on UserProfile; (2) ForcePasswordChangeMiddleware isn't in
    MIDDLEWARE at all; (3) CustomPasswordChangeView.form_valid "clears" it
    by setting a transient attribute on User (no such field — save()
    persists nothing).

    Expected: a logged-in user with profile.must_change_password=True is
    redirected to the password-change page, and completing the change
    persistently clears the flag.
    Actual (current code): no redirect; flag never clears -> test FAILS,
    demonstrating M11.
    """
    from django.test import Client
    from apps.account.models import UserProfile

    user = User.objects.create_user(username="m11user", password="s3cret-pass")
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.must_change_password = True
    profile.save()

    client = Client()
    client.force_login(user)

    # Defects 1+2: the middleware must be active and read the profile flag.
    resp = client.get("/dashboard/")
    assert resp.status_code == 302, (
        "expected redirect to the password-change page, "
        f"got {resp.status_code}"
    )
    assert "password_change" in resp.url, f"unexpected redirect target: {resp.url}"

    # Defect 3: completing the change must persistently clear the flag.
    resp = client.post(
        "/accounts/password_change/",
        {
            "old_password": "s3cret-pass",
            "new_password1": "n3w-s3cret-pass!",
            "new_password2": "n3w-s3cret-pass!",
        },
    )
    assert resp.status_code == 302, (
        f"password change should succeed, got {resp.status_code}"
    )
    profile.refresh_from_db()
    assert profile.must_change_password is False, (
        "must_change_password was not persistently cleared"
    )


@pytest.mark.django_db
def test_m12_jwt_login_uses_authenticate_and_updates_last_login():
    """M12 — JWT login bypasses authenticate().

    apps/account/api/jwt_serializers.py — fetches the user and calls
    check_password directly: the AUTHENTICATION_BACKENDS chain is bypassed,
    no user_login_failed signal fires on bad passwords, and last_login is
    never updated for JWT users.

    Expected: validate() delegates credential checking to
    django.contrib.auth.authenticate (so user_login_failed fires on bad
    passwords) and updates last_login on success.
    Actual (current code): check_password called directly; authenticate()
    never invoked; last_login stays None -> test FAILS, demonstrating M12.
    """
    from django.contrib.auth.signals import user_login_failed
    from rest_framework.test import APIRequestFactory

    fired = []

    def receiver(sender, credentials, request, **kwargs):
        fired.append(credentials)

    user_login_failed.connect(receiver, weak=False)
    try:
        user = User.objects.create_user(username="m12user", password="s3cret-pass")
        # Mirror production: DRF views always put the request in context.
        request = APIRequestFactory().post("/api/v1/token/")

        # Wrong password → user_login_failed must fire (via authenticate()).
        serializer = FlexibleTokenObtainPairSerializer(
            context={"request": request}
        )
        with pytest.raises(AuthenticationFailed):
            serializer.validate({"username": "m12user", "password": "wrong-pass"})
        assert fired, "user_login_failed signal did not fire on bad password"

        # Right password → last_login updated, tokens returned.
        serializer = FlexibleTokenObtainPairSerializer(
            context={"request": request}
        )
        data = serializer.validate(
            {"username": "m12user", "password": "s3cret-pass"}
        )
        user.refresh_from_db()
        assert user.last_login is not None, "last_login was not updated"
        assert "access" in data and "refresh" in data
    finally:
        user_login_failed.disconnect(receiver)


@pytest.mark.django_db
def test_h7_rotation_retry_returns_identical_tokens():
    """H7 review (PR #106/#107): a retried rotation must return the SAME
    tokens issued at rotation time, not newly minted ones.

    Two tabs refreshing at once (or a retry after a network blip) present
    the already-rotated R1. The server must answer with the R2 cookies from
    the first rotation so concurrent retries converge instead of each
    minting a fresh session.
    """
    from django.conf import settings
    from django.core.cache import cache
    from rest_framework_simplejwt.tokens import RefreshToken

    cache.clear()
    user = User.objects.create_user(username="h7sametokens", password="<redacted>")
    refresh = RefreshToken.for_user(user)
    refresh_cookie = settings.SIMPLE_JWT.get("AUTH_COOKIE_REFRESH", "refresh_token")
    access_cookie = settings.SIMPLE_JWT.get("AUTH_COOKIE", "access_token")

    client = APIClient()
    client.cookies[refresh_cookie] = str(refresh)

    resp1 = client.post("/api/v1/auth/refresh/")
    assert resp1.status_code == 200, f"first refresh failed: {getattr(resp1, 'data', None)}"
    r1_access = resp1.cookies[access_cookie].value
    r1_refresh = resp1.cookies[refresh_cookie].value
    assert r1_refresh != str(refresh), "rotation should issue a new refresh token"

    # Client never received R2: retries with the blacklisted R1.
    client.cookies[refresh_cookie] = str(refresh)
    resp2 = client.post("/api/v1/auth/refresh/")
    assert resp2.status_code == 200, (
        f"retried refresh should succeed, got {resp2.status_code}: {getattr(resp2, 'data', None)}"
    )
    assert resp2.cookies[access_cookie].value == r1_access, (
        "retry must return the SAME access token, not a newly minted one"
    )
    assert resp2.cookies[refresh_cookie].value == r1_refresh, (
        "retry must return the SAME refresh token, not a newly minted one"
    )


@pytest.mark.django_db
def test_h7_logout_blacklisted_token_gets_no_grace():
    """H7/H6 interaction (PR #106/#107 blocker): a refresh token blacklisted
    by LOGOUT must not be revived by the H7 reuse-grace window.

    Logout blacklists the refresh token exactly like rotation does, but it
    never writes the rotation reuse cache. Presenting the logged-out token
    within 60s must 401 — otherwise logout on a shared computer hands the
    next visitor a brand-new session.
    """
    from django.conf import settings
    from django.core.cache import cache
    from rest_framework_simplejwt.tokens import RefreshToken

    cache.clear()
    user = User.objects.create_user(username="h7logout", password="<redacted>")
    refresh = RefreshToken.for_user(user)
    refresh_cookie = settings.SIMPLE_JWT.get("AUTH_COOKIE_REFRESH", "refresh_token")

    client = APIClient()
    client.cookies[refresh_cookie] = str(refresh)

    resp = client.post("/api/v1/auth/logout/")
    assert resp.status_code == 200, f"logout failed: {getattr(resp, 'data', None)}"

    # Immediately present the logged-out refresh token: no grace, 401.
    client.cookies[refresh_cookie] = str(refresh)
    resp2 = client.post("/api/v1/auth/refresh/")
    assert resp2.status_code == 401, (
        "a logout-blacklisted refresh token must NOT be honored by the "
        f"reuse grace window, got {resp2.status_code}: {getattr(resp2, 'data', None)}"
    )


@pytest.mark.django_db
def test_force_password_change_middleware_exempts_logout_and_static():
    """Review #107 (core/settings.py:221 blocker): ForcePasswordChangeMiddleware
    must not gate logout or static assets.

    must_change_password defaults True and nothing ever cleared it, so on
    deploy nearly every user would be flagged. A flagged user must still be
    able to log out, and the password-change page needs its CSS/JS. Other
    pages still redirect to password_change.
    """
    from django.test import RequestFactory
    from django.contrib.auth.models import AnonymousUser
    from apps.account.models import UserProfile
    from apps.pantry.middleware import ForcePasswordChangeMiddleware

    user = User.objects.create_user(username="pwflag", password="<redacted>")
    UserProfile.objects.create(user=user, must_change_password=True)

    def get_response(request):
        from django.http import HttpResponse
        return HttpResponse("ok")

    mw = ForcePasswordChangeMiddleware(get_response)
    factory = RequestFactory()

    for path in ("/accounts/logout/", "/static/css/app.css"):
        request = factory.get(path)
        request.user = user
        resp = mw(request)
        assert resp.status_code == 200, (
            f"{path} must not be gated by the forced-change redirect, "
            f"got {resp.status_code}"
        )

    request = factory.get("/some-page/")
    request.user = user
    resp = mw(request)
    assert resp.status_code == 302, (
        f"other pages must still redirect to password_change, got {resp.status_code}"
    )
    assert "/password_change/" in resp["Location"]


@pytest.mark.django_db
def test_login_failure_count_survives_cookie_clear(client):
    """Review #107 (core/urls.py:39): login failure count must live in the
    cache, not the session.

    Old code kept login_failures in the session — clearing the session
    cookie reset the count and the captcha never appeared. New code counts
    per username/IP in the cache.
    """
    from django.core.cache import cache

    cache.clear()
    user = User.objects.create_user(username="bruteforce", password="<redacted>")

    # 3 failed attempts (wrong password).
    for _ in range(3):
        resp = client.post(
            "/login/",
            {"username": "bruteforce", "password": "definitely-wrong"},
        )
        assert resp.status_code == 200  # re-rendered, not logged in

    # Attacker clears the session cookie...
    client.cookies.clear()

    # ...but the captcha still shows, because the count is in the cache.
    resp = client.get("/login/")
    assert resp.status_code == 200
    assert resp.context["show_captcha"] is True, (
        "captcha must appear after 3 failures even with a fresh session"
    )


@pytest.mark.django_db
def test_login_honors_next_parameter(client):
    """Review #107 (core/urls.py:39): custom_login_view must honor ?next=.

    Old code always redirected to participant_dashboard, so login_required
    redirects (e.g. from /admin/...) lost their destination. next must be
    validated with url_has_allowed_host_and_scheme — open redirects out.
    """
    from django.core.cache import cache

    cache.clear()
    User.objects.create_user(username="nextuser", password="<redacted>")

    # ?next= is exposed to the template (hidden field).
    resp = client.get("/login/?next=/admin/")
    assert resp.status_code == 200
    assert resp.context["next"] == "/admin/"

    # Successful login follows a safe next URL...
    resp = client.post(
        "/login/?next=/admin/",
        {"username": "nextuser", "password": "<redacted>"},
    )
    assert resp.status_code == 302, f"login failed: {resp.status_code}"
    assert resp["Location"] == "/admin/", f"next not honored: {resp['Location']}"

    # ...but not an off-site one.
    client.logout()
    cache.clear()
    resp = client.post(
        "/login/",
        {"username": "nextuser", "password": "<redacted>", "next": "http://evil.example/"},
    )
    assert resp.status_code == 302
    assert "evil.example" not in resp["Location"], (
        f"open redirect! Location: {resp['Location']}"
    )


@pytest.mark.django_db
def test_jwt_login_checks_password_before_disabled_notice():
    """Review #107 (minor): is_active must be checked AFTER authenticate().

    Old order ran the is_active check first, so 'Account is disabled' was
    returned without the password ever being validated (no authenticate()
    call, no user_login_failed signal). New order: authenticate() runs
    first; the disabled notice comes only after it fails.
    """
    from django.contrib.auth.signals import user_login_failed
    from rest_framework_simplejwt.exceptions import AuthenticationFailed
    from apps.account.api.jwt_serializers import FlexibleTokenObtainPairSerializer

    user = User.objects.create_user(username="disabled1", password="<redacted>")
    user.is_active = False
    user.save(update_fields=["is_active"])

    signals = []
    def _receiver(sender, credentials, **kwargs):
        signals.append(credentials)
    user_login_failed.connect(_receiver, weak=False)
    try:
        from rest_framework.test import APIRequestFactory
        rf_request = APIRequestFactory().post("/api/token/")
        serializer = FlexibleTokenObtainPairSerializer(
            context={"request": rf_request}
        )
        try:
            serializer.validate({"username": "disabled1", "password": "<redacted>"})
        except AuthenticationFailed as exc:
            detail = exc.detail
            code = detail.get("code") if isinstance(detail, dict) else detail
        else:
            code = None
    finally:
        user_login_failed.disconnect(_receiver)

    assert code == "account_disabled", f"expected account_disabled, got {code}"
    assert signals, (
        "authenticate() must run before the disabled check so a failed "
        "password attempt still fires user_login_failed"
    )
