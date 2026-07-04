"""Copy the existing grace_message into the modeltranslation _en column."""
from django.db import migrations
from django.db.models import F


def copy_to_english_column(apps, schema_editor):
    ProgramSettings = apps.get_model('core', 'ProgramSettings')
    ProgramSettings.objects.update(grace_message_en=F('grace_message'))


def blank_english_column(apps, schema_editor):
    ProgramSettings = apps.get_model('core', 'ProgramSettings')
    ProgramSettings.objects.update(grace_message_en=None)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_programsettings_grace_message_en_and_more'),
    ]

    operations = [
        migrations.RunPython(copy_to_english_column, blank_english_column),
    ]
