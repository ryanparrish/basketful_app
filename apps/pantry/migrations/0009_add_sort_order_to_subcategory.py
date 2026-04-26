"""
Migration: add sort_order to Subcategory model.
Data migration populates sort_order alphabetically within each parent category
using gaps of 10 so newly created subcategories (default=0) float to the top.
"""
from django.db import migrations, models


def populate_subcategory_sort_order(apps, schema_editor):
    Category = apps.get_model('pantry', 'Category')
    for category in Category.objects.prefetch_related('subcategories').order_by('id'):
        for idx, sub in enumerate(category.subcategories.order_by('name'), start=1):
            sub.sort_order = idx * 10
            sub.save(update_fields=['sort_order'])


def reverse_populate(apps, schema_editor):
    apps.get_model('pantry', 'Subcategory').objects.all().update(sort_order=0)


class Migration(migrations.Migration):

    dependencies = [
        ('pantry', '0008_populate_sort_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='subcategory',
            name='sort_order',
            field=models.IntegerField(
                default=0,
                help_text='Pick sequence within parent category. 0 = top (newly created). Reorder via drag-and-drop in admin.',
            ),
        ),
        migrations.RunPython(populate_subcategory_sort_order, reverse_populate),
    ]
