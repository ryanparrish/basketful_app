"""
Tests for the can_bypass_order_transitions permission.

Verifies that:
  - Superusers can move orders freely between confirmed/packing/completed.
  - Users explicitly granted the permission can do the same.
  - Regular staff users cannot bypass; the order is skipped.
  - cancelled is terminal even for bypass users.
  - pending follows normal transition rules even for bypass users.
  - Bypass transitions that *are* also in ALLOWED_TRANSITIONS still work.
"""

import pytest
from django.contrib.auth.models import Permission
from rest_framework.test import APIClient

from apps.orders.tests.factories import (
    OrderFactory,
    ParticipantFactory,
    UserFactory,
)

BULK_URL = '/api/v1/orders/bulk_update_status/'


def _make_staff_client(superuser=False):
    user = UserFactory(is_staff=True, is_superuser=superuser)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


def _make_order(status):
    """Create an order with the given status, using the signal-created account."""
    participant = ParticipantFactory()
    account = participant.accountbalance
    return OrderFactory(account=account, status=status)


def _give_bypass_perm(user):
    perm = Permission.objects.get(codename='can_bypass_order_transitions')
    user.user_permissions.add(perm)
    # Refresh from DB so Django's permission cache is invalidated.
    from django.contrib.auth.models import User as AuthUser
    return AuthUser.objects.get(pk=user.pk)


@pytest.mark.django_db
class TestBypassPermission:
    """Suite for the can_bypass_order_transitions escape hatch."""

    def test_superuser_can_bypass_completed_to_packing(self):
        """Superuser may move a completed order back to packing (normally blocked)."""
        client, _ = _make_staff_client(superuser=True)
        order = _make_order('completed')

        resp = client.post(BULK_URL, {'order_ids': [order.id], 'new_status': 'packing'}, format='json')

        assert resp.status_code == 200, resp.data
        assert resp.data['updated_count'] == 1
        assert resp.data['skipped_count'] == 0

        order.refresh_from_db()
        assert order.status == 'packing'

    def test_superuser_can_bypass_packing_to_confirmed(self):
        """Superuser can walk packing → confirmed (bypasses forward-only rule)."""
        client, _ = _make_staff_client(superuser=True)
        order = _make_order('packing')

        resp = client.post(BULK_URL, {'order_ids': [order.id], 'new_status': 'confirmed'}, format='json')

        assert resp.status_code == 200
        assert resp.data['updated_count'] == 1
        order.refresh_from_db()
        assert order.status == 'confirmed'

    def test_explicit_permission_grants_bypass(self):
        """A non-superuser explicitly granted the permission can bypass."""
        _, user = _make_staff_client()
        user = _give_bypass_perm(user)

        client = APIClient()
        client.force_authenticate(user=user)
        order = _make_order('completed')

        resp = client.post(BULK_URL, {'order_ids': [order.id], 'new_status': 'packing'}, format='json')

        assert resp.status_code == 200, resp.data
        assert resp.data['updated_count'] == 1
        order.refresh_from_db()
        assert order.status == 'packing'

    def test_regular_staff_cannot_bypass(self):
        """Regular staff (no bypass perm, not superuser) is blocked from out-of-order transition."""
        client, _ = _make_staff_client(superuser=False)
        order = _make_order('completed')

        resp = client.post(BULK_URL, {'order_ids': [order.id], 'new_status': 'packing'}, format='json')

        assert resp.status_code == 200
        assert resp.data['updated_count'] == 0
        assert resp.data['skipped_count'] == 1

        order.refresh_from_db()
        assert order.status == 'completed'  # unchanged

    def test_cancelled_is_terminal_for_bypass_user(self):
        """Even with bypass, cancelled → active is not allowed."""
        _, user = _make_staff_client()
        user = _give_bypass_perm(user)

        client = APIClient()
        client.force_authenticate(user=user)
        order = _make_order('cancelled')

        resp = client.post(BULK_URL, {'order_ids': [order.id], 'new_status': 'confirmed'}, format='json')

        assert resp.status_code == 200
        assert resp.data['skipped_count'] == 1
        assert resp.data['updated_count'] == 0

        order.refresh_from_db()
        assert order.status == 'cancelled'

    def test_pending_follows_normal_rules_for_bypass_user(self):
        """Bypass users cannot skip pending → packing directly."""
        client, _ = _make_staff_client(superuser=True)
        order = _make_order('pending')

        resp = client.post(BULK_URL, {'order_ids': [order.id], 'new_status': 'packing'}, format='json')

        assert resp.status_code == 200
        assert resp.data['skipped_count'] == 1
        assert resp.data['updated_count'] == 0

        order.refresh_from_db()
        assert order.status == 'pending'

    def test_pending_to_confirmed_works_for_bypass_user(self):
        """Bypass users can still use normal allowed transitions (pending → confirmed)."""
        client, _ = _make_staff_client(superuser=True)
        order = _make_order('pending')

        resp = client.post(BULK_URL, {'order_ids': [order.id], 'new_status': 'confirmed'}, format='json')

        assert resp.status_code == 200
        assert resp.data['updated_count'] == 1
        order.refresh_from_db()
        assert order.status == 'confirmed'

    def test_bypass_warning_logged(self, caplog):
        """Bypass transitions emit a WARNING-level log entry."""
        import logging
        client, _ = _make_staff_client(superuser=True)
        order = _make_order('completed')

        with caplog.at_level(logging.WARNING, logger='apps.orders.api.views'):
            client.post(BULK_URL, {'order_ids': [order.id], 'new_status': 'packing'}, format='json')

        bypass_logs = [r for r in caplog.records if 'bypass' in r.message.lower()]
        assert bypass_logs, "Expected a WARNING log for bypass transition"
        assert str(order.id) in bypass_logs[0].message

    def test_non_staff_cannot_access_bulk_endpoint(self):
        """Endpoint requires staff; non-staff gets 403."""
        user = UserFactory(is_staff=False)
        client = APIClient()
        client.force_authenticate(user=user)
        order = _make_order('confirmed')

        resp = client.post(BULK_URL, {'order_ids': [order.id], 'new_status': 'packing'}, format='json')

        assert resp.status_code == 403

