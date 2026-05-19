from decimal import Decimal
from django.db import migrations


def backfill_hygiene_ratio(apps, schema_editor):
    HygieneSettings = apps.get_model("account", "HygieneSettings")
    HygieneSettings.objects.update(
        hygiene_ratio=Decimal("1") / Decimal("3")
    )


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0009_participant_preferred_language_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_hygiene_ratio, migrations.RunPython.noop),
    ]
