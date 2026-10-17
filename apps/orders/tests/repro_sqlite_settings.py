"""Test-only settings shim for running the repro suite on SQLite.

CI runs Postgres; this VM has none. The only Postgres-only migration is
apps/pantry/migrations/0005_enable_trigram_extension.py (CREATE EXTENSION
pg_trgm), which cannot run on SQLite — so the TrigramExtension operation
is patched to a no-op when the connection vendor is sqlite. Everything
else (including the migration graph) runs normally. No model uses
Postgres-only fields (only standard JSONField), so this is faithful for
the logic-level bugs under test.

Requires psycopg2-binary in the venv (import-time only; never connects).

Usage:
    DJANGO_SETTINGS_MODULE=apps.orders.tests.repro_sqlite_settings pytest ...
"""

from core.settings import *  # noqa: F401,F403

# No-op the Postgres trigram extension on SQLite. The migration module
# itself is untouched (see module docstring).
from django.contrib.postgres.operations import TrigramExtension  # noqa: E402

_orig_trigram_forwards = TrigramExtension.database_forwards
_orig_trigram_backwards = TrigramExtension.database_backwards


def _trigram_forwards(self, app_label, schema_editor, from_state, to_state):
    if schema_editor.connection.vendor == "sqlite":
        return
    return _orig_trigram_forwards(self, app_label, schema_editor, from_state, to_state)


def _trigram_backwards(self, app_label, schema_editor, from_state, to_state):
    if schema_editor.connection.vendor == "sqlite":
        return
    return _orig_trigram_backwards(self, app_label, schema_editor, from_state, to_state)


TrigramExtension.database_forwards = _trigram_forwards
TrigramExtension.database_backwards = _trigram_backwards
