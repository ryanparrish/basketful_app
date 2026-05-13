"""
Tests for the participant API — diaper_count field.

Covers: BEH-205, BEH-206

BEH-205 regression:
    PATCH /api/v1/participants/{id}/ with {"diaper_count": N} must persist
    to the database. Previously the admin frontend sent {"infants": N} (wrong
    field name), so the value was silently ignored by DRF.

BEH-206 contract test:
    Sending {"infants": N} (the old broken key) must NOT change diaper_count.
    This confirms DRF's behaviour of ignoring unknown keys — acting as a
    permanent canary: if someone adds an "infants" alias to the serializer,
    this test will break and prompt review.
"""
import pytest
from rest_framework.test import APIClient

from apps.account.models import Participant
from apps.orders.tests.factories import ParticipantFactory, UserFactory, VoucherSettingFactory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# BEH-205 / BEH-206
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestParticipantDiaperCountAPI:
    """
    PATCH /api/v1/participants/{id}/ correctly reads and writes diaper_count.
    Covers: BEH-205, BEH-206
    """

    def test_patch_diaper_count_persists_to_database(self, staff_client):
        """BEH-205 — PATCH {"diaper_count": 3} saves 3 to Participant.diaper_count."""
        # Arrange
        participant = ParticipantFactory(diaper_count=0)

        # Act
        response = staff_client.patch(
            f'/api/v1/participants/{participant.id}/',
            {'diaper_count': 3},
            format='json',
        )

        # Assert
        assert response.status_code == 200, response.data
        participant.refresh_from_db()
        assert participant.diaper_count == 3

    def test_patch_diaper_count_is_reflected_in_response(self, staff_client):
        """BEH-205 (cont.) — the updated value is returned in the PATCH response body."""
        # Arrange
        participant = ParticipantFactory(diaper_count=0)

        # Act
        response = staff_client.patch(
            f'/api/v1/participants/{participant.id}/',
            {'diaper_count': 2},
            format='json',
        )

        # Assert
        assert response.status_code == 200
        assert response.data['diaper_count'] == 2

    def test_patch_unknown_infants_key_does_not_change_diaper_count(self, staff_client):
        """
        BEH-206 — PATCH {"infants": 5} must NOT update diaper_count.

        DRF silently ignores unknown serializer fields. This test acts as a
        canary: if someone adds 'infants' as a field alias, this test will
        break and force a conscious decision about the field contract.
        """
        # Arrange
        participant = ParticipantFactory(diaper_count=1)
        original_count = participant.diaper_count

        # Act
        response = staff_client.patch(
            f'/api/v1/participants/{participant.id}/',
            {'infants': 99},
            format='json',
        )

        # Assert — request succeeds (unknown fields are not an error) ...
        assert response.status_code == 200
        # ... but diaper_count is unchanged
        participant.refresh_from_db()
        assert participant.diaper_count == original_count

    def test_get_response_contains_diaper_count_not_infants(self, staff_client):
        """
        Contract test — the API always exposes the field as 'diaper_count'.
        If the key were ever renamed in the serializer, this breaks immediately.
        """
        # Arrange
        participant = ParticipantFactory(diaper_count=2)

        # Act
        response = staff_client.get(f'/api/v1/participants/{participant.id}/')

        # Assert
        assert response.status_code == 200
        assert 'diaper_count' in response.data
        assert 'infants' not in response.data
        assert response.data['diaper_count'] == 2
