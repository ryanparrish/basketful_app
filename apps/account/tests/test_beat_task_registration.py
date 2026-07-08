"""Every beat-scheduled task must be registered on the Celery app.

Regression test for the order-window notification outage: the
``notify_participants_order_window_opened`` task lived in a submodule that
nothing imported, so the worker never registered it and beat's dispatches
were silently discarded every 10 minutes. Task submodules must be imported
by their package ``__init__.py`` for ``autodiscover_tasks()`` to see them.
"""

import pytest
from django.conf import settings

from core.celery import app


@pytest.fixture(scope='module')
def registered_task_names():
    app.loader.import_default_modules()
    return set(app.tasks)


def beat_schedule_task_names():
    return sorted(
        entry['task'] for entry in settings.CELERY_BEAT_SCHEDULE.values()
    )


@pytest.mark.parametrize('task_name', beat_schedule_task_names())
def test_beat_scheduled_task_is_registered(task_name, registered_task_names):
    assert task_name in registered_task_names, (
        f"'{task_name}' is in CELERY_BEAT_SCHEDULE but not registered with "
        f"the Celery app — the worker will discard every dispatch. Import "
        f"its module from the tasks package __init__.py."
    )
