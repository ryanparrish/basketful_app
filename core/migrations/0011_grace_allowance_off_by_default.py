"""Grace allowance is one site-wide switch, off by default.

Turns it off on existing installs too; staff turn it back on in Settings →
Grace. Not reversed: the earlier per-install value isn't kept.
"""
from django.db import migrations, models


def turn_grace_off(apps, schema_editor):
    ProgramSettings = apps.get_model("core", "ProgramSettings")
    ProgramSettings.objects.update(grace_enabled=False)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_emailsettings_url_overrides"),
    ]

    operations = [
        migrations.AlterField(
            model_name="programsettings",
            name="grace_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Site-wide switch. On: every order may go up to grace_amount over "
                    "balance, at checkout and at confirmation. Off: nothing over "
                    "balance goes through. There is no per-program or per-order "
                    "override."
                ),
            ),
        ),
        migrations.RunPython(turn_grace_off, migrations.RunPython.noop),
    ]
