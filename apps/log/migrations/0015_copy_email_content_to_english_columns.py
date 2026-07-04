"""
Copy existing EmailType content into the modeltranslation *_en columns and
seed Spanish subjects for the known email types.

Spanish bodies are intentionally left blank: they are long, staff-editable
TinyMCE templates and fall back to English until staff enter a translation
in the admin. Seeding only the subject gives Spanish-speaking participants
a recognizable inbox line without shipping machine-translated body copy.
"""
from django.db import migrations
from django.db.models import F

SPANISH_SUBJECTS = {
    'onboarding': '¡Bienvenido a Love Your Neighbor!',
    'password_reset': 'Establezca su contraseña',
    'order_confirmation': 'Su pedido ha sido realizado',
    'voucher_notification': 'Tiene un nuevo vale',
    'order_window_opened': 'Su período para hacer pedidos está abierto — {{ program_name }}',
}


def copy_and_seed(apps, schema_editor):
    EmailType = apps.get_model('log', 'EmailType')

    EmailType.objects.update(
        subject_en=F('subject'),
        html_content_en=F('html_content'),
        text_content_en=F('text_content'),
    )

    for name, subject_es in SPANISH_SUBJECTS.items():
        EmailType.objects.filter(name=name).update(subject_es=subject_es)


def unseed(apps, schema_editor):
    EmailType = apps.get_model('log', 'EmailType')
    EmailType.objects.update(
        subject_en=None,
        html_content_en=None,
        text_content_en=None,
        subject_es=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('log', '0014_emailtype_html_content_en_emailtype_html_content_es_and_more'),
    ]

    operations = [
        migrations.RunPython(copy_and_seed, unseed),
    ]
