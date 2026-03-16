"""
Migration: add sort_order to Category and Product models.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pantry', '0006_tag_product_tags'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='sort_order',
            field=models.IntegerField(
                default=0,
                help_text='Pick sequence for packing lists. 0 = top (newly created). Reorder via drag-and-drop in admin.',
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='sort_order',
            field=models.IntegerField(
                default=0,
                help_text='Pick sequence within category for packing lists. 0 = top (newly created). Reorder via drag-and-drop in admin.',
            ),
        ),
    ]
