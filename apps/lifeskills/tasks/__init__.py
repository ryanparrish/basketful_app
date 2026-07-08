"""Tasks for lifeskills app.

Celery's ``autodiscover_tasks()`` only imports this package, not its
submodules — each must be imported here or its tasks never register.
"""
from apps.lifeskills.tasks import program_pause  # noqa: F401
