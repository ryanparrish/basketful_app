"""
django-modeltranslation registrations for core models.

grace_message is staff-entered text shown verbatim to participants by the
cart validation endpoint, so it needs a per-language column like catalog
content does.
"""
from modeltranslation.translator import TranslationOptions, register

from .models import ProgramSettings


@register(ProgramSettings)
class ProgramSettingsTranslationOptions(TranslationOptions):
    fields = ('grace_message',)
