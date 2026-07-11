"""Onboarding email leads with the username again (Issue #83).

Staff and participants use the Django username day to day — migration
0010 switched the email to the customer number, which is what Issue #83
reports as confusing. Both credentials authenticate (see
FlexibleTokenObtainPairSerializer), so the email now leads with the
username and keeps the customer number as a secondary note.

Uses targeted string replacement on the live rows (not a wholesale
overwrite) so staff edits to the surrounding template are preserved.
"""
from django.db import migrations


HTML_REPLACEMENTS = [
    (
        '<p class="login-label">Your Login Number</p>',
        '<p class="login-label">Your Username</p>',
    ),
    (
        '<p class="login-value">{{ participant_customer_number }}</p>',
        '<p class="login-value">{{ user.username }}</p>',
    ),
    (
        "Save this — you'll type it in every time you log in.</p>",
        "Save this — you'll type it in every time you log in.<br>"
        "You can also log in with your Customer Number: "
        "{{ participant_customer_number }}</p>",
    ),
    (
        '<p>Log in with your login number</p>',
        '<p>Log in with your username</p>',
    ),
]

TEXT_REPLACEMENTS = [
    (
        'YOUR LOGIN NUMBER: {{ participant_customer_number }}',
        'YOUR USERNAME: {{ user.username }}',
    ),
    (
        "Keep this — you'll type it in every time you log in.",
        "Keep this — you'll type it in every time you log in.\n"
        "You can also log in with your Customer Number: "
        "{{ participant_customer_number }}",
    ),
]


def apply_username_wording(apps, schema_editor):
    EmailType = apps.get_model('log', 'EmailType')
    onboarding = EmailType.objects.filter(name='onboarding').first()
    if onboarding is None:
        return

    changed_fields = []
    for field in ('html_content', 'html_content_en', 'html_content_es'):
        value = getattr(onboarding, field, None)
        if not value:
            continue
        for old, new in HTML_REPLACEMENTS:
            value = value.replace(old, new)
        if value != getattr(onboarding, field):
            setattr(onboarding, field, value)
            changed_fields.append(field)

    for field in ('text_content', 'text_content_en', 'text_content_es'):
        value = getattr(onboarding, field, None)
        if not value:
            continue
        for old, new in TEXT_REPLACEMENTS:
            value = value.replace(old, new)
        if value != getattr(onboarding, field):
            setattr(onboarding, field, value)
            changed_fields.append(field)

    if changed_fields:
        onboarding.save(update_fields=changed_fields)


class Migration(migrations.Migration):

    dependencies = [
        ('log', '0016_seed_low_inventory_alert_email_type'),
    ]

    operations = [
        migrations.RunPython(apply_username_wording, migrations.RunPython.noop),
    ]
