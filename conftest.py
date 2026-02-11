"""
Global pytest configuration for Basketful app.

This configures Celery to run in eager mode during tests,
preventing connection attempts to RabbitMQ broker.
"""
import pytest
from django.conf import settings


@pytest.fixture(scope='session', autouse=True)
def configure_celery_for_tests():
    """
    Configure Celery to run tasks eagerly (synchronously) during tests.
    This prevents connection errors to RabbitMQ broker.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
