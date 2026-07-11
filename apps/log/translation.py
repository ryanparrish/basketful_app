"""
django-modeltranslation registration for EmailType.

Per-language content columns (subject_es, html_content_es, ...) on the
single EmailType row per email name — NOT row-per-language, because
EmailLog dedup (has_email_been_sent) and retry_failed_emails both key on
one EmailType instance per name; split rows would let a Spanish onboarding
email bypass the already-sent guard.

The send task (apps/account/tasks/email.py) renders inside
translation.override(participant.preferred_language), which makes these
descriptors resolve the right column with English fallback.
"""
from modeltranslation.translator import TranslationOptions, register

from .models import EmailType


@register(EmailType)
class EmailTypeTranslationOptions(TranslationOptions):
    # design_json/content_source are the email studio's per-language
    # editor state: each language has its own block design, and code
    # edits mark only that language's design stale.
    fields = (
        'subject', 'html_content', 'text_content',
        'design_json', 'content_source',
    )
