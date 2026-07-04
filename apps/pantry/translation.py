"""
django-modeltranslation registrations for participant-visible catalog text.

Registration adds per-language columns (name_en, name_es, ...) generated
from settings.LANGUAGES. Reads of the base field (product.name) resolve to
the active request language and fall back to English when the translation
is blank — so the participant API serializers need no changes.

Adding a language later: add it to LANGUAGES and run makemigrations.
"""
from modeltranslation.translator import TranslationOptions, register

from .models import Category, Product, Subcategory, Tag


@register(Product)
class ProductTranslationOptions(TranslationOptions):
    fields = ('name', 'description')


@register(Category)
class CategoryTranslationOptions(TranslationOptions):
    fields = ('name',)


@register(Subcategory)
class SubcategoryTranslationOptions(TranslationOptions):
    fields = ('name',)


@register(Tag)
class TagTranslationOptions(TranslationOptions):
    fields = ('name', 'description')
