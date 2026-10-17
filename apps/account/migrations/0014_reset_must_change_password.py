"""Reset stale must_change_password flags (review #107).

UserProfile.must_change_password defaults True, and nothing ever cleared
it (the old view hit NoReverseMatch and set the attribute on User, not the
profile). Registering ForcePasswordChangeMiddleware without this migration
would redirect essentially every existing user to the password-change page
on deploy. Staff can re-flag individuals via the admin when needed.

Not reversible: the pre-migration per-user values are unknowable.
"""
from django.db import migrations


def reset_flags(apps, schema_editor):
    UserProfile = apps.get_model("account", "UserProfile")
    UserProfile.objects.filter(must_change_password=True).update(
        must_change_password=False
    )


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0013_alter_participant_assigned_coach"),
    ]

    operations = [
        migrations.RunPython(reset_flags, migrations.RunPython.noop),
    ]
