"""Log tasks package.

Celery's ``autodiscover_tasks()`` only imports this package, not its
submodules — each must be imported here or its tasks never register.
"""
from apps.log.tasks import logs  # noqa: F401
