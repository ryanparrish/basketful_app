"""Seed the existing 'Inventory Managers' group as the default notify_groups
recipient, preserving current alert behavior for installs that relied on the
previously-hardcoded group name.
"""
from django.db import migrations


def seed_notify_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    LowInventoryAlertSettings = apps.get_model('pantry', 'LowInventoryAlertSettings')

    group, _ = Group.objects.get_or_create(name='Inventory Managers')
    settings_row, _ = LowInventoryAlertSettings.objects.get_or_create(
        pk=1, defaults={'threshold': 45, 'enabled': True}
    )
    settings_row.notify_groups.add(group)


def unseed_notify_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    LowInventoryAlertSettings = apps.get_model('pantry', 'LowInventoryAlertSettings')

    try:
        group = Group.objects.get(name='Inventory Managers')
        settings_row = LowInventoryAlertSettings.objects.get(pk=1)
    except (Group.DoesNotExist, LowInventoryAlertSettings.DoesNotExist):
        return
    settings_row.notify_groups.remove(group)


class Migration(migrations.Migration):

    dependencies = [
        ('pantry', '0014_low_inventory_alert_notify_recipients'),
    ]

    operations = [
        migrations.RunPython(seed_notify_group, unseed_notify_group),
    ]
