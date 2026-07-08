"""
Regression tests for deleting a coach who has assigned participants.

Production incident: DELETE /api/v1/coaches/<id>/ raised ProtectedError
and returned a 500. Participant.assigned_coach was CASCADE, so deleting a
coach tried to cascade-delete their participants (and balances/vouchers);
the delete was only stopped because those participants had orders, whose
PROTECT FK on AccountBalance blocked the cascade.

Now assigned_coach is SET_NULL: deleting a coach simply unassigns their
participants, and every related record survives.
"""
import pytest
from rest_framework.test import APIClient

from apps.lifeskills.models import LifeskillsCoach
from apps.account.models import Participant
from apps.orders.models import Order
from apps.orders.tests.factories import (
    OrderFactory,
    ParticipantFactory,
    UserFactory,
    VoucherSettingFactory,
)


@pytest.fixture(autouse=True)
def voucher_setting():
    return VoucherSettingFactory(active=True)


@pytest.fixture
def staff_client():
    client = APIClient()
    client.force_authenticate(user=UserFactory(is_staff=True))
    return client


@pytest.mark.django_db
class TestCoachDelete:

    def test_deleting_coach_unassigns_participants_and_keeps_their_data(self, staff_client):
        coach = LifeskillsCoach.objects.create(name='Coach Kim', email='kim@example.com')
        participant = ParticipantFactory(assigned_coach=coach)
        order = OrderFactory(account=participant.accountbalance, status='completed')

        response = staff_client.delete(f'/api/v1/coaches/{coach.id}/')

        assert response.status_code == 204, getattr(response, 'data', None)
        assert not LifeskillsCoach.objects.filter(pk=coach.pk).exists()
        # The participant and their financial records survive, unassigned
        participant.refresh_from_db()
        assert participant.assigned_coach is None
        assert Order.objects.filter(pk=order.pk).exists()
        assert Participant.objects.filter(pk=participant.pk).exists()

    def test_non_staff_cannot_delete_coach(self):
        coach = LifeskillsCoach.objects.create(name='Coach Lee', email='lee@example.com')
        participant = ParticipantFactory()
        client = APIClient()
        client.force_authenticate(user=participant.user)

        response = client.delete(f'/api/v1/coaches/{coach.id}/')

        assert response.status_code == 403
        assert LifeskillsCoach.objects.filter(pk=coach.pk).exists()
