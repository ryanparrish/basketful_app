import pytest
from django.core.management import call_command


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """
    Custom database setup to handle circular migration dependencies.
    
    This fixture runs migrations with --run-syncdb to create tables
    from models directly, bypassing the circular dependency issue in
    the initial migrations.
    """
    with django_db_blocker.unblock():
        # Create all tables from current models
        call_command('migrate', '--run-syncdb', verbosity=0)
        # Mark all migrations as applied
        call_command('migrate', '--fake', verbosity=0)
