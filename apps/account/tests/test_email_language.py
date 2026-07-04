"""
Tests that emails render in the participant's preferred language.

- Spanish participant → subject_es (with English fallback for blank body)
- English participant → English subject
- Blank Spanish subject → English fallback
- Dedup still works across languages (single EmailType row)
"""
import pytest
from django.core import mail

from apps.account.tasks.email import send_email_by_type
from apps.log.models import EmailType
from apps.orders.tests.factories import ParticipantFactory, VoucherSettingFactory


@pytest.fixture(autouse=True)
def voucher_setting():
    return VoucherSettingFactory(active=True)


@pytest.fixture
def bilingual_email_type():
    return EmailType.objects.create(
        name='test_notice',
        display_name='Test Notice',
        subject='Hello {{ user.username }}',
        subject_en='Hello {{ user.username }}',
        subject_es='Hola {{ user.username }}',
        html_content='<p>Hello</p>',
        html_content_en='<p>Hello</p>',
        text_content='Hello',
        text_content_en='Hello',
        is_active=True,
    )


@pytest.mark.django_db
class TestEmailLanguage:

    def test_spanish_participant_gets_spanish_subject(self, bilingual_email_type):
        participant = ParticipantFactory(preferred_language='es')
        participant.user.email = 'es@example.com'
        participant.user.save(update_fields=['email'])

        assert send_email_by_type(participant.user.id, 'test_notice') is True
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject.startswith('Hola ')
        # Blank Spanish body falls back to English
        assert 'Hello' in mail.outbox[0].body

    def test_english_participant_gets_english_subject(self, bilingual_email_type):
        participant = ParticipantFactory(preferred_language='en')
        participant.user.email = 'en@example.com'
        participant.user.save(update_fields=['email'])

        assert send_email_by_type(participant.user.id, 'test_notice') is True
        assert mail.outbox[0].subject.startswith('Hello ')

    def test_blank_spanish_subject_falls_back_to_english(self, bilingual_email_type):
        EmailType.objects.filter(name='test_notice').update(subject_es=None)
        participant = ParticipantFactory(preferred_language='es')
        participant.user.email = 'fallback@example.com'
        participant.user.save(update_fields=['email'])

        assert send_email_by_type(participant.user.id, 'test_notice') is True
        assert mail.outbox[0].subject.startswith('Hello ')

    def test_dedup_is_language_independent(self, bilingual_email_type):
        """One EmailType row means the already-sent guard can't be bypassed
        by a language switch."""
        participant = ParticipantFactory(preferred_language='en')
        participant.user.email = 'dedup@example.com'
        participant.user.save(update_fields=['email'])

        assert send_email_by_type(participant.user.id, 'test_notice') is True

        participant.preferred_language = 'es'
        participant.save(update_fields=['preferred_language'])

        assert send_email_by_type(participant.user.id, 'test_notice') is False
        assert len(mail.outbox) == 1
