"""
Issue #111: the login throttle could be bypassed with a made-up
X-Forwarded-For header.

DRF's default get_ident() used the whole X-Forwarded-For header as the
client's identity, and our proxies append to whatever the client sent. A
new forged value per request meant a fresh 5-per-minute bucket each time.
Throttles now identify clients through core.client_ip.get_client_ip.
"""
import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import RequestFactory
from rest_framework import throttling as drf_throttling
from rest_framework.test import APIClient

from core.client_ip import get_client_ip
from core.throttling import ClientIPIdentMixin

LOGIN = "/api/v1/auth/login/"
REAL_CLIENT = "203.0.113.50"
NODEBALANCER = "192.168.255.10"   # what nginx sees as REMOTE_ADDR's peer
NGINX = "127.0.0.1"


@pytest.fixture(autouse=True)
def _fresh_cache(settings):
    settings.RECAPTCHA_PRIVATE_KEY = "test-private-key"
    cache.clear()
    yield
    cache.clear()


def _meta(**headers):
    return RequestFactory().get("/", **headers)


# ---------------------------------------------------------------------------
# get_client_ip
# ---------------------------------------------------------------------------

class TestGetClientIp:

    def test_prefers_cloudflare_header(self):
        request = _meta(
            HTTP_CF_CONNECTING_IP=REAL_CLIENT,
            HTTP_X_FORWARDED_FOR=f"6.6.6.6, {REAL_CLIENT}, {NODEBALANCER}",
            REMOTE_ADDR=NGINX,
        )
        assert get_client_ip(request) == REAL_CLIENT

    def test_forged_forwarded_for_is_ignored_when_cf_header_present(self):
        a = _meta(HTTP_CF_CONNECTING_IP=REAL_CLIENT,
                  HTTP_X_FORWARDED_FOR="1.1.1.1")
        b = _meta(HTTP_CF_CONNECTING_IP=REAL_CLIENT,
                  HTTP_X_FORWARDED_FOR="2.2.2.2")
        assert get_client_ip(a) == get_client_ip(b) == REAL_CLIENT

    def test_without_cf_header_uses_last_forwarded_hop(self):
        # The nearest proxy appends the address it saw last; anything the
        # client sent lands to its left.
        request = _meta(HTTP_X_FORWARDED_FOR=f"6.6.6.6, {REAL_CLIENT}",
                        REMOTE_ADDR=NGINX)
        assert get_client_ip(request) == REAL_CLIENT

    def test_falls_back_to_remote_addr(self):
        assert get_client_ip(_meta(REMOTE_ADDR="10.1.2.3")) == "10.1.2.3"

    def test_garbage_header_values_are_ignored(self):
        request = _meta(HTTP_CF_CONNECTING_IP="not-an-ip",
                        HTTP_X_FORWARDED_FOR="also, garbage",
                        REMOTE_ADDR="10.1.2.3")
        assert get_client_ip(request) == "10.1.2.3"

    def test_ipv6_is_normalised(self):
        request = _meta(HTTP_CF_CONNECTING_IP="2001:DB8:0:0:0:0:0:1")
        assert get_client_ip(request) == "2001:db8::1"

    def test_header_is_configurable(self, settings):
        settings.CLIENT_IP_HEADER = "HTTP_X_REAL_IP"
        request = _meta(HTTP_X_REAL_IP=REAL_CLIENT,
                        HTTP_CF_CONNECTING_IP="9.9.9.9")
        assert get_client_ip(request) == REAL_CLIENT

    def test_trusted_header_can_be_disabled(self, settings):
        settings.CLIENT_IP_HEADER = ""
        request = _meta(HTTP_CF_CONNECTING_IP="9.9.9.9",
                        HTTP_X_FORWARDED_FOR=REAL_CLIENT)
        assert get_client_ip(request) == REAL_CLIENT

    def test_none_request(self):
        assert get_client_ip(None) is None


# ---------------------------------------------------------------------------
# The bypass itself (acceptance test from the issue)
# ---------------------------------------------------------------------------

def _login(forged_xff, cf_ip=REAL_CLIENT):
    return APIClient().post(
        LOGIN,
        {"username": "target", "password": "wrong-guess",
         "recaptcha_token": "t"},
        format="json",
        REMOTE_ADDR=NGINX,
        HTTP_CF_CONNECTING_IP=cf_ip,
        HTTP_X_FORWARDED_FOR=f"{forged_xff}, {cf_ip}, {NODEBALANCER}",
    )


@pytest.mark.django_db
def test_forged_forwarded_for_values_share_one_login_bucket():
    User.objects.create_user(username="target", password="right-password")
    statuses = [_login(forged_xff=f"10.0.0.{n}").status_code
                for n in range(6)]
    assert 429 not in statuses[:5], statuses
    assert statuses[5] == 429, statuses


@pytest.mark.django_db
def test_different_real_clients_get_separate_buckets():
    User.objects.create_user(username="target", password="right-password")
    for n in range(5):
        _login(forged_xff="1.1.1.1", cf_ip="203.0.113.1")
    assert _login(forged_xff="1.1.1.1", cf_ip="203.0.113.1").status_code == 429
    assert _login(forged_xff="1.1.1.1", cf_ip="203.0.113.2").status_code != 429


# ---------------------------------------------------------------------------
# Guard: no throttle may fall back to DRF's forgeable get_ident()
# ---------------------------------------------------------------------------

def _all_subclasses(cls):
    for sub in cls.__subclasses__():
        yield sub
        yield from _all_subclasses(sub)


def test_every_project_throttle_uses_trusted_client_ip(settings):
    from django.urls import get_resolver
    from django.utils.module_loading import import_string

    get_resolver().url_patterns  # import every view (and its throttles)
    for path in settings.REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES']:
        assert issubclass(import_string(path), ClientIPIdentMixin), path

    offenders = sorted(
        f"{cls.__module__}.{cls.__qualname__}"
        for cls in set(_all_subclasses(drf_throttling.BaseThrottle))
        if cls.__module__.startswith(("apps.", "core."))
        and not issubclass(cls, ClientIPIdentMixin)
    )
    assert offenders == [], (
        "Subclass core.throttling, not rest_framework.throttling (#111): "
        f"{offenders}"
    )
