"""Shared fixtures for apps/log tests.

The email tests assert against the EmailType rows seeded by data
migrations. Data-migration rows do NOT survive a database flush: any
TransactionTestCase in the suite (e.g. apps/lifeskills/tests/
test_program_pause.py) truncates all tables when it finishes, so tests
that run after it see an empty EmailType table — locally the ordering
may hide this, in CI it surfaced as EmailType.DoesNotExist.

Per the project convention (see CLAUDE.md: create test data explicitly,
never rely on database state), `seeded_email_types` re-runs the actual
migration seed functions when the rows are missing. Reusing the real
migration code keeps the content byte-identical to production, so the
wording-migration assertions still test the real thing.
"""
import importlib

import pytest
from django.apps import apps as django_apps


def _migration(name):
    return importlib.import_module(f'apps.log.migrations.{name}')


@pytest.fixture
def seeded_email_types(db):
    """Ensure the migration-seeded EmailType rows exist."""
    from apps.log.models import EmailType

    if not EmailType.objects.filter(name='onboarding').exists():
        _migration('0005_seed_email_types').seed_email_types(django_apps, None)
        _migration('0011_fix_email_template_escaped_quotes').fix_email_templates(django_apps, None)
        _migration('0017_onboarding_email_username_wording').apply_username_wording(django_apps, None)
    if not EmailType.objects.filter(name='order_window_opened').exists():
        _migration('0011_seed_order_window_opened_email_type').seed_order_window_opened_email_type(django_apps, None)
    if not EmailType.objects.filter(name='low_inventory_alert').exists():
        _migration('0016_seed_low_inventory_alert_email_type').seed_low_inventory_alert_email_type(django_apps, None)
