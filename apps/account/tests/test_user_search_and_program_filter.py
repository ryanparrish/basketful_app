"""
Tests for the Users API's search and Participant-program filter.

Adds `?search=` coverage (already backed by SearchFilter) and the new
`?participant__program=<id>` filter plus `program_name` field, so staff can
search/filter the Users admin list by the program their linked Participant
belongs to.
"""
import pytest
from rest_framework.test import APIClient

from apps.orders.tests.factories import (
    ParticipantFactory,
    ProgramFactory,
    UserFactory,
    VoucherSettingFactory,
)


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
class TestUserSearch:
    def test_search_matches_username(self, staff_client):
        ParticipantFactory(name="Alice Johnson", user=UserFactory(username="Alice Johnson-bloom"))
        ParticipantFactory(name="Bob Smith", user=UserFactory(username="Bob Smith-anchor"))

        response = staff_client.get("/api/v1/users/?search=Alice")

        usernames = [u["username"] for u in response.data["results"]]
        assert usernames == ["Alice Johnson-bloom"]


@pytest.mark.django_db
class TestUserProgramFilter:
    def test_filters_users_by_participant_program(self, staff_client):
        monday = ProgramFactory(name="Monday Morning")
        tuesday = ProgramFactory(name="Tuesday Afternoon")

        in_program = ParticipantFactory(program=monday)
        other_program = ParticipantFactory(program=tuesday)

        response = staff_client.get(f"/api/v1/users/?participant__program={monday.id}")

        user_ids = {u["id"] for u in response.data["results"]}
        assert user_ids == {in_program.user_id}
        assert other_program.user_id not in user_ids

    def test_program_name_reflects_linked_participant(self, staff_client):
        monday = ProgramFactory(name="Monday Morning")
        participant = ParticipantFactory(program=monday)

        response = staff_client.get(f"/api/v1/users/{participant.user_id}/")

        assert response.data["program_name"] == "Monday Morning"

    def test_program_name_is_none_for_user_without_participant(self, staff_client):
        user = UserFactory(is_staff=True)

        response = staff_client.get(f"/api/v1/users/{user.id}/")

        assert response.data["program_name"] is None
