"""
Tests for the email design studio backend (Stage 2):
  1. design_json/content_source per-language columns round-trip via API.
  2. send-test renders a draft with sample data and emails the requesting
     staff user, logged as EmailLog(is_test=True) with a [TEST] subject.
  3. Test sends never poison the real pipeline: the already-sent dedup
     guard ignores them and the DLQ never re-dispatches a failed test.
"""
import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from rest_framework.test import APIClient

from apps.account.tasks.email import has_email_been_sent
from apps.log.models import EmailLog, EmailType

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _email_types(seeded_email_types):
    """Migration-seeded EmailTypes, resilient to DB flushes (see conftest)."""

SAMPLE_DESIGN = {
    'root': {
        'type': 'EmailLayout',
        'data': {'childrenIds': ['block-1']},
    },
    'block-1': {
        'type': 'Text',
        'data': {'props': {'text': 'Hello {{ user.first_name }}'}},
    },
}


@pytest.fixture
def staff_user():
    return User.objects.create_user(
        username='studio-staff', email='studio@example.com', is_staff=True
    )


@pytest.fixture
def staff_client(staff_user):
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


def onboarding_url(suffix=''):
    email_type = EmailType.objects.get(name='onboarding')
    return f'/api/v1/email-types/{email_type.pk}/{suffix}'


class TestDesignFieldsRoundTrip:

    def test_design_json_and_content_source_per_language(self, staff_client):
        response = staff_client.patch(
            onboarding_url(),
            {
                'design_json_en': SAMPLE_DESIGN,
                'content_source_en': 'design',
            },
            format='json',
        )
        assert response.status_code == 200

        email_type = EmailType.objects.get(name='onboarding')
        assert email_type.design_json_en == SAMPLE_DESIGN
        assert email_type.content_source_en == 'design'
        # Spanish untouched.
        assert email_type.design_json_es is None

        data = staff_client.get(onboarding_url()).data
        assert data['design_json_en'] == SAMPLE_DESIGN
        assert data['content_source_en'] == 'design'


class TestSendTest:

    def test_send_test_delivers_to_requesting_user(self, staff_client, staff_user):
        mail.outbox.clear()
        response = staff_client.post(
            onboarding_url('send-test/'),
            {
                'subject': 'Draft subject for {{ user.first_name }}',
                'html_content': '<p>Draft body {{ participant_customer_number }}</p>',
                'language': 'en',
            },
            format='json',
        )
        assert response.status_code == 200
        assert staff_user.email in response.data['detail']

        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert message.to == [staff_user.email]
        assert message.subject == '[TEST] Draft subject for Maria'
        assert 'C-BKM-7' in message.alternatives[0][0]

        log_entry = EmailLog.objects.get(user=staff_user, is_test=True)
        assert log_entry.status == 'sent'

    def test_send_test_with_broken_template_returns_400(self, staff_client, staff_user):
        mail.outbox.clear()
        response = staff_client.post(
            onboarding_url('send-test/'),
            {'html_content': '{% for x in %}broken{% endfor %}'},
            format='json',
        )
        assert response.status_code == 400
        assert not mail.outbox
        assert not EmailLog.objects.filter(user=staff_user, is_test=True).exists()

    def test_send_test_requires_staff(self):
        client = APIClient()
        client.force_authenticate(
            user=User.objects.create_user(username='pleb', email='p@example.com')
        )
        assert client.post(onboarding_url('send-test/'), {}, format='json').status_code == 403

    def test_send_test_without_email_address_is_rejected(self):
        client = APIClient()
        client.force_authenticate(
            user=User.objects.create_user(username='no-email', email='', is_staff=True)
        )
        response = client.post(onboarding_url('send-test/'), {}, format='json')
        assert response.status_code == 400


class TestTestSendIsolation:

    def test_dedup_guard_ignores_test_sends(self, staff_user):
        email_type = EmailType.objects.get(name='password_reset')
        EmailLog.objects.create(
            user=staff_user, email_type=email_type,
            subject='[TEST] hi', status='sent', is_test=True,
        )
        assert has_email_been_sent(staff_user, email_type) is False

        EmailLog.objects.create(
            user=staff_user, email_type=email_type,
            subject='hi', status='sent',
        )
        assert has_email_been_sent(staff_user, email_type) is True

    def test_dlq_never_redispatches_failed_test_sends(self, staff_user, monkeypatch):
        from apps.account.tasks import email as email_tasks

        email_type = EmailType.objects.get(name='onboarding')
        EmailLog.objects.create(
            user=staff_user, email_type=email_type,
            subject='[TEST] boom', status='failed', is_test=True,
        )

        dispatched = []
        monkeypatch.setattr(
            email_tasks.send_email_by_type, 'delay',
            lambda *args, **kwargs: dispatched.append((args, kwargs)),
        )
        email_tasks.retry_failed_emails()
        assert dispatched == []
