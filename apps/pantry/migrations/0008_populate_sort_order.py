"""
Data migration: populate sort_order on Category and Product alphabetically,
using gaps of 10 (10, 20, 30, ...) so newly created items (default=0)
appear at the top, and future inserts have room without a full reindex.
"""
from django.db import migrations


def populate_sort_order(apps, schema_editor):
    Category = apps.get_model('pantry', 'Category')
    Product = apps.get_model('pantry', 'Product')

    # Assign sort_order to categories in alphabetical order
    for idx, category in enumerate(Category.objects.order_by('name'), start=1):
        category.sort_order = idx * 10
        category.save(update_fields=['sort_order'])

    # Assign sort_order to products in alphabetical order (globally)
    # Products within the same category will be reindexed by the drag UI,
    # but start with a clean global alpha baseline.
    for idx, product in enumerate(Product.objects.order_by('name'), start=1):
        product.sort_order = idx * 10
        product.save(update_fields=['sort_order'])


def reverse_populate(apps, schema_editor):
    Category = apps.get_model('pantry', 'Category')
    Product = apps.get_model('pantry', 'Product')
    Category.objects.all().update(sort_order=0)
    Product.objects.all().update(sort_order=0)


class Migration(migrations.Migration):

    dependencies = [
        ('pantry', '0007_add_sort_order_to_category_and_product'),
    ]

    operations = [
        migrations.RunPython(populate_sort_order, reverse_populate),
    ]
