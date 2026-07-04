"""
Copy existing catalog text into the modeltranslation *_en columns.

modeltranslation resolves product.name to the active language column with
English fallback; without this copy every pre-existing row would have an
empty name_en and fall through to the raw column only for the default
language, breaking non-default-language fallback.
"""
from django.db import migrations
from django.db.models import F


def copy_to_english_columns(apps, schema_editor):
    Product = apps.get_model('pantry', 'Product')
    Category = apps.get_model('pantry', 'Category')
    Subcategory = apps.get_model('pantry', 'Subcategory')
    Tag = apps.get_model('pantry', 'Tag')

    Product.objects.update(name_en=F('name'), description_en=F('description'))
    Category.objects.update(name_en=F('name'))
    Subcategory.objects.update(name_en=F('name'))
    Tag.objects.update(name_en=F('name'), description_en=F('description'))


def blank_english_columns(apps, schema_editor):
    Product = apps.get_model('pantry', 'Product')
    Category = apps.get_model('pantry', 'Category')
    Subcategory = apps.get_model('pantry', 'Subcategory')
    Tag = apps.get_model('pantry', 'Tag')

    Product.objects.update(name_en=None, description_en=None)
    Category.objects.update(name_en=None)
    Subcategory.objects.update(name_en=None)
    Tag.objects.update(name_en=None, description_en=None)


class Migration(migrations.Migration):

    dependencies = [
        ('pantry', '0011_category_name_en_category_name_es_and_more'),
    ]

    operations = [
        migrations.RunPython(copy_to_english_columns, blank_english_columns),
    ]
