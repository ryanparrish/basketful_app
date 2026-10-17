"""Reproduction test for confirmed Basketful bug H10 (2026-10-16 review).

The test asserts the CORRECT behavior and FAILS on the current code,
demonstrating the bug. Do NOT "fix" this test to pass — fix the code.

Environment: run on SQLite via the test-only settings shim:
    DATABASE_URL="sqlite:////tmp/test_db.sqlite3" SECRET_KEY=x HASHIDS_SALT=y \
    DJANGO_SETTINGS_MODULE=apps.orders.tests.repro_sqlite_settings \
    python -m pytest core/tests/test_bug_repros_2026_10_16.py
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from apps.lifeskills.models import Program
from core.api.serializers import OrderWindowSettingsSerializer
from core.models import OrderWindowSettings


@pytest.mark.django_db
def test_h10_global_window_status_reflects_program_windows():
    """H10 — public order-window status always reports "closed".

    core/api/serializers.py (OrderWindowSettingsSerializer.get_is_open and
    friends) — `from apps.lifeskills.models import Lifeskills` imports a class
    that does not exist; the ImportError is swallowed by
    `except Exception: return False`. is_open is permanently False and
    next_opens_at/next_closes_at permanently None, even mid-window, on a
    public AllowAny endpoint.

    Expected: when a program's window is open per the modern per-program
    engine (core/utils.get_program_window_status), the global serializer
    reports is_open=True with real next open/close timestamps.
    Actual (current code): is_open False, timestamps None -> test FAILS,
    demonstrating H10.
    """
    from core.utils import get_program_window_status

    settings_obj = OrderWindowSettings.get_settings()
    settings_obj.enabled = True
    settings_obj.hours_before_class = 48
    settings_obj.hours_before_close = 1
    settings_obj.save()

    # Freeze to a Friday midday (UTC): a program meeting today at 14:00 has
    # its (meeting - 48h, meeting - 1h) window open right now.
    with freeze_time("2026-10-16 12:00:00"):
        program = Program.objects.create(
            name="H10 Program",
            MeetingDay="friday",
            meeting_time="14:00:00",
        )

        # Sanity: the modern per-program engine sees an open window.
        assert get_program_window_status(program)["window_status"] == "open"

        data = OrderWindowSettingsSerializer(settings_obj).data
        assert data["is_open"] is True, (
            "global window status should be open while a program window is open"
        )
        assert data["next_opens_at"] is not None
        assert data["next_closes_at"] is not None
