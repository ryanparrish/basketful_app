"""
Tests for the per-session cart_token used by the legacy cart's client-side
localStorage scoping (apps/pantry/views.py::get_cart_token).

The token exists to stop a shared/kiosk device from handing one
participant's leftover cart to the next participant who logs in on it —
these tests verify the actual security-relevant property (different
sessions get different tokens, the same session is stable) rather than
just that a string of some kind gets returned.
"""
import hashlib
import re

from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from apps.account.models import Participant
from apps.pantry.views import get_cart_token
from apps.pantry.tests.factories import VoucherSettingFactory

User = get_user_model()

CART_TOKEN_RE = re.compile(r'^[0-9a-f]{16}$')


def _make_participant(username):
    user = User.objects.create_user(
        username=username, password='test_password_123', email=f'{username}@test.com'
    )
    return Participant.objects.create(user=user, name=username, email=f'{username}@test.com')


class GetCartTokenUnitTest(TestCase):
    """Direct unit tests against get_cart_token(request), bypassing the
    view/template so the session_key-missing edge case can be forced
    deterministically rather than hoped for via the test client."""

    def setUp(self):
        self.factory = RequestFactory()

    def _request_with_session(self, session=None):
        request = self.factory.get('/create-order/')
        request.session = session if session is not None else SessionStore()
        return request

    def test_returns_a_16_char_hex_token(self):
        request = self._request_with_session()
        token = get_cart_token(request)
        self.assertRegex(token, CART_TOKEN_RE)

    def test_token_is_the_sha256_of_the_session_key_truncated_to_16(self):
        request = self._request_with_session()
        token = get_cart_token(request)

        expected = hashlib.sha256(request.session.session_key.encode()).hexdigest()[:16]
        self.assertEqual(token, expected)

    def test_creates_a_session_key_when_none_exists_yet(self):
        session = SessionStore()
        self.assertIsNone(session.session_key)
        request = self._request_with_session(session)

        get_cart_token(request)

        self.assertIsNotNone(request.session.session_key)

    def test_two_different_sessions_get_two_different_tokens(self):
        # This is the actual property the token exists for: a shared/kiosk
        # device must not compute the same localStorage key for two
        # different participants' sessions.
        request_a = self._request_with_session()
        request_b = self._request_with_session()

        token_a = get_cart_token(request_a)
        token_b = get_cart_token(request_b)

        self.assertNotEqual(request_a.session.session_key, request_b.session.session_key)
        self.assertNotEqual(token_a, token_b)

    def test_same_session_key_always_produces_the_same_token(self):
        session = SessionStore()
        session.save()
        session_key = session.session_key

        token_1 = get_cart_token(self._request_with_session(SessionStore(session_key=session_key)))
        token_2 = get_cart_token(self._request_with_session(SessionStore(session_key=session_key)))

        self.assertEqual(token_1, token_2)


class CartTokenInCreateOrderViewTest(TestCase):
    """End-to-end: the real create_order view actually renders a usable,
    per-session cart_token into the template context."""

    def setUp(self):
        VoucherSettingFactory()
        _make_participant('cart_token_user_a')
        _make_participant('cart_token_user_b')

    def test_cart_token_is_present_and_well_formed_in_context(self):
        client = Client()
        client.login(username='cart_token_user_a', password='test_password_123')

        response = client.get(reverse('create_order'))

        self.assertIn('cart_token', response.context)
        self.assertRegex(response.context['cart_token'], CART_TOKEN_RE)

    def test_cart_token_is_stable_across_requests_in_the_same_session(self):
        client = Client()
        client.login(username='cart_token_user_a', password='test_password_123')

        first = client.get(reverse('create_order')).context['cart_token']
        second = client.get(reverse('create_order')).context['cart_token']

        self.assertEqual(first, second)

    def test_different_participants_get_different_cart_tokens(self):
        client_a = Client()
        client_a.login(username='cart_token_user_a', password='test_password_123')
        token_a = client_a.get(reverse('create_order')).context['cart_token']

        client_b = Client()
        client_b.login(username='cart_token_user_b', password='test_password_123')
        token_b = client_b.get(reverse('create_order')).context['cart_token']

        self.assertNotEqual(token_a, token_b)

    def test_cart_token_is_embedded_in_the_rendered_page_for_the_client_script(self):
        client = Client()
        client.login(username='cart_token_user_a', password='test_password_123')

        response = client.get(reverse('create_order'))

        expected_token = response.context['cart_token']
        self.assertContains(response, f'const cartToken = "{expected_token}"')
