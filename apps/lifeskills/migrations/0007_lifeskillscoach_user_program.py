"""
Migration: Add user + program to LifeskillsCoach and create 'Lifeskills Coach' RBAC group.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def create_coach_group(apps, schema_editor):
    """Create 'Lifeskills Coach' group with view-only permissions for relevant models."""
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    group, _ = Group.objects.get_or_create(name='Lifeskills Coach')

    # (app_label, codename) — scoped lookups avoid multi-app collisions
    perms_to_add = [
        ('lifeskills', 'view_lifeskillscoach'),
        ('lifeskills', 'change_lifeskillscoach'),
        ('lifeskills', 'view_program'),
    ]
    # Also add view permissions for participants and orders using codename-only lookup
    # (app_label may vary depending on installed apps config)
    codename_fallbacks = [
        'view_participant',
        'view_order',
        'view_orderitem',
    ]

    for app_label, codename in perms_to_add:
        perm = Permission.objects.filter(
            content_type__app_label=app_label, codename=codename
        ).first()
        if perm:
            group.permissions.add(perm)

    for codename in codename_fallbacks:
        for perm in Permission.objects.filter(codename=codename):
            group.permissions.add(perm)


def remove_coach_group(apps, schema_editor):
    """Reverse: remove the group."""
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name='Lifeskills Coach').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('lifeskills', '0006_programpause_resync_fields'),
        ('auth', '0012_alter_user_first_name_max_length'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='lifeskillscoach',
            name='user',
            field=models.OneToOneField(
                blank=True,
                help_text='Django user account for this coach (grants login access to admin)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='coach_profile',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='lifeskillscoach',
            name='program',
            field=models.ForeignKey(
                blank=True,
                help_text='Program this coach is assigned to',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='coaches',
                to='lifeskills.program',
            ),
        ),
        migrations.RunPython(create_coach_group, remove_coach_group),
    ]
