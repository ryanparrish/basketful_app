"""
Point the nightly pause beat entry at archive_ended_pauses (#141).

Beat uses django_celery_beat's DatabaseScheduler, which adds rows for new
CELERY_BEAT_SCHEDULE entries but never removes old ones. Without this, the
old 'cleanup-expired-pause-flags' row would keep firing a task that no
longer exists, and pauses would stop being archived.
"""
from django.db import migrations

OLD_TASK = 'apps.lifeskills.tasks.program_pause.cleanup_expired_pause_flags'
NEW_TASK = 'apps.lifeskills.tasks.program_pause.archive_ended_pauses'
OLD_NAME = 'cleanup-expired-pause-flags'
NEW_NAME = 'archive-ended-pauses'


def point_beat_at_archive_task(apps, schema_editor):
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    PeriodicTask.objects.filter(task=OLD_TASK).update(name=NEW_NAME, task=NEW_TASK)


def point_beat_at_cleanup_task(apps, schema_editor):
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    PeriodicTask.objects.filter(task=NEW_TASK).update(name=OLD_NAME, task=OLD_TASK)


class Migration(migrations.Migration):

    dependencies = [
        ('lifeskills', '0008_coach_programs_m2m'),
        ('django_celery_beat', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(point_beat_at_archive_task, point_beat_at_cleanup_task),
    ]
