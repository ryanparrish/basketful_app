"""
Tests for the bulk-reset-password participant API action.

`ParticipantViewSet.bulk_reset_password` locks each user row and defers the
password-reset email dispatch to transaction commit, so overlapping resets
for the same participant can't leave a stale reset token in an already-sent
email (see apps/account/api/views.py).
"""
import pytest
from rest_framework.test import APIClient

from apps.account.models import Participant, UserProfile
from apps.orders.tests.factories import ParticipantFactory, UserFactory, VoucherSettingFactory


@pytest.fixture(autouse=True)
def voucher_setting():
    """Active VoucherSetting is required by ParticipantFactory's balance hook."""
    return VoucherSettingFactory(active=True)


@pytest.fixture
def staff_client():
    """Authenticated API client with is_staff=True."""
    user = UserFactory(is_staff=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestBulkResetPassword:
    """POST /api/v1/participants/bulk-reset-password/"""

    def test_resets_password_and_sends_email(
        self, staff_client, mocker, django_capture_on_commit_callbacks
    ):
        mock_send_email_task = mocker.patch(
            "apps.account.api.views.send_password_reset_email.delay"
        )
        participant = ParticipantFactory()
        original_hash = participant.user.password

        with django_capture_on_commit_callbacks(execute=True):
            response = staff_client.post(
                "/api/v1/participants/bulk-reset-password/",
                {"ids": [participant.id]},
                format="json",
            )

        assert response.status_code == 200

        participant.user.refresh_from_db()
        assert participant.user.password != original_hash

        profile = UserProfile.objects.get(user=participant.user)
        assert profile.must_change_password is True

        # force=True bypasses the lifetime "already sent" email dedup —
        # each reset generates a genuinely new password that must be delivered
        mock_send_email_task.assert_called_once_with(participant.user.id, force=True)

    def test_skips_participants_without_user(self, staff_client, mocker):
        mock_send_email_task = mocker.patch(
            "apps.account.api.views.send_password_reset_email.delay"
        )
        participant = ParticipantFactory()
        participant.user = None
        participant.save(update_fields=["user"])

        response = staff_client.post(
            "/api/v1/participants/bulk-reset-password/",
            {"ids": [participant.id]},
            format="json",
        )

        assert response.status_code == 200
        assert "Skipped 1" in response.data["message"]
        mock_send_email_task.assert_not_called()

    def test_email_dispatch_waits_for_commit(self, staff_client, mocker):
        """The Celery dispatch must not fire until the row lock is released."""
        mock_send_email_task = mocker.patch(
            "apps.account.api.views.send_password_reset_email.delay"
        )
        participant = ParticipantFactory()

        # Without capturing on_commit callbacks, the deferred dispatch never
        # runs inside a single non-transactional test — proving it really is
        # deferred rather than fired inline during the loop.
        staff_client.post(
            "/api/v1/participants/bulk-reset-password/",
            {"ids": [participant.id]},
            format="json",
        )
        mock_send_email_task.assert_not_called()
