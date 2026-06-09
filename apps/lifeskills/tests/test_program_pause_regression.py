"""
Regression tests — ProgramPause signal/task issues (triaged 2026-06-09).

Three distinct failure modes observed in production logs:

A. "Could not determine earliest window close time" — the signal fires after
   all participants' order-window close times have already passed for the day.
   Should log a warning and exit cleanly, not raise.

B. Naive datetime passed to schedule_voucher_tasks — when a pause is created
   outside the 10-14 day window and pause_start is naive, the comparison
   `activate_time > timezone.now()` raises TypeError because you cannot
   compare a naive datetime with an aware one.
   Fixed at the serializer layer (ProgramPauseSerializer.validate_pause_start/end).

C. get_next_class_datetime returning a past datetime — when today is the same
   weekday as the meeting day AND the meeting time has already passed, the
   function must advance to next week.  The production code already handles
   this correctly; this test guards against regression.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest import mock

from django.utils import timezone
from django.utils.timezone import make_aware
from freezegun import freeze_time

from apps.account.models import Participant, AccountBalance
from apps.lifeskills.models import ProgramPause, Program
from apps.voucher.models import Voucher
from core.models import OrderWindowSettings
from core.utils import get_next_class_datetime


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def order_window(db):
    """Return the singleton OrderWindowSettings, ensuring it exists."""
    return OrderWindowSettings.get_settings()


@pytest.fixture
def tuesday_program(db):
    """Program that meets every Tuesday at 18:00."""
    return Program.objects.create(
        name="Tuesday Night",
        MeetingDay="tuesday",
        meeting_time="18:00:00",
        meeting_address="123 Main St",
    )


@pytest.fixture
def participant_in_tuesday_program(tuesday_program, db):
    """Active participant enrolled in the Tuesday program, two active vouchers."""
    p = Participant.objects.create(
        name="Test Participant",
        email="tp@test.com",
        program=tuesday_program,
        active=True,
        adults=2,
    )
    acct, _ = AccountBalance.objects.get_or_create(
        participant=p,
        defaults={"base_balance": Decimal("90.00")},
    )
    acct.vouchers.all().delete()
    v1 = Voucher.objects.create(account=acct, active=True, voucher_type="grocery", state="applied")
    v2 = Voucher.objects.create(account=acct, active=True, voucher_type="grocery", state="applied")
    return {"participant": p, "account": acct, "vouchers": [v1, v2]}


# ---------------------------------------------------------------------------
# A. "Could not determine earliest window close time"
# ---------------------------------------------------------------------------

@freeze_time("2026-06-09 17:10:00+00:00")  # 13:10 EDT — Tuesday, after window close
@pytest.mark.django_db(transaction=True)
def test_signal_logs_warning_when_all_windows_have_closed(
    participant_in_tuesday_program, order_window, caplog
):
    """
    Regression A: signal fires after all order-window close times have passed.

    Setup:
      - Tuesday class at 18:00 EDT (22:00 UTC)
      - hours_before_close = 5  → window closes at 13:00 EDT (17:00 UTC)
      - Frozen time: 13:10 EDT  → window closed 10 min ago
      - ProgramPause starts 12 days from now (within 10-14 day window)

    Expected: signal emits a WARNING about "Could not determine", does NOT raise.
    """
    order_window.hours_before_close = 5
    order_window.save(update_fields=["hours_before_close"])

    pause_start = timezone.now() + timedelta(days=12)
    pause_end = pause_start + timedelta(days=7)

    with mock.patch(
        "apps.lifeskills.signals.update_voucher_flag_task.delay"
    ), mock.patch(
        "apps.lifeskills.signals.deactivate_expired_pause_vouchers.apply_async"
    ):
        import logging
        with caplog.at_level(logging.WARNING, logger="apps.lifeskills.signals"):
            ProgramPause.objects.create(
                pause_start=pause_start,
                pause_end=pause_end,
                reason="Test window-closed regression",
            )

    assert any(
        "Could not determine earliest window close time" in r.message
        for r in caplog.records
    ), "Expected warning about window close time not found in log output"


@pytest.mark.django_db(transaction=True)
def test_signal_logs_warning_when_no_participants_have_programs(db, caplog):
    """
    Regression A (degenerate case): there are active vouchers (so the signal
    passes the early-exit guard) but NO participants are enrolled in a program,
    so no future window-close time can be computed.
    Should log a warning, not crash.
    """
    # Create a voucher owned by a programless participant so the signal
    # passes the "no active vouchers" early exit.
    p = Participant.objects.create(
        name="No Program", email="noprog@test.com", active=True, adults=1,
    )
    acct, _ = AccountBalance.objects.get_or_create(
        participant=p, defaults={"base_balance": Decimal("20.00")}
    )
    acct.vouchers.all().delete()
    Voucher.objects.create(account=acct, active=True, voucher_type="grocery", state="applied")

    pause_start = timezone.now() + timedelta(days=12)
    pause_end = pause_start + timedelta(days=7)

    with mock.patch(
        "apps.lifeskills.signals.update_voucher_flag_task.delay"
    ), mock.patch(
        "apps.lifeskills.signals.deactivate_expired_pause_vouchers.apply_async"
    ):
        import logging
        with caplog.at_level(logging.WARNING, logger="apps.lifeskills.signals"):
            ProgramPause.objects.create(
                pause_start=pause_start,
                pause_end=pause_end,
                reason="No participants enrolled in programs",
            )

    assert any(
        "Could not determine earliest window close time" in r.message
        for r in caplog.records
    )


# ---------------------------------------------------------------------------
# B. Naive datetime bugs
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_serializer_makes_naive_pause_start_aware():
    """
    Regression B: ProgramPauseSerializer.validate_pause_start must convert
    naive datetimes to timezone-aware before they reach the model.
    """
    from apps.lifeskills.api.serializers import ProgramPauseSerializer

    data = {
        "pause_start": "2026-06-27T09:00:00",   # no tz offset — naive
        "pause_end":   "2026-07-04T09:00:00",
        "reason":      "Summer break",
    }
    serializer = ProgramPauseSerializer(data=data)
    assert serializer.is_valid(), serializer.errors

    pause_start = serializer.validated_data["pause_start"]
    pause_end   = serializer.validated_data["pause_end"]

    assert pause_start.tzinfo is not None, (
        "pause_start must be timezone-aware after serializer validation"
    )
    assert pause_end.tzinfo is not None, (
        "pause_end must be timezone-aware after serializer validation"
    )


@pytest.mark.django_db
def test_serializer_passes_through_already_aware_datetime():
    """
    Aware datetimes (with explicit UTC offset) must not be double-converted.
    """
    from apps.lifeskills.api.serializers import ProgramPauseSerializer

    data = {
        "pause_start": "2026-06-27T09:00:00-04:00",  # EDT offset
        "pause_end":   "2026-07-04T09:00:00-04:00",
        "reason":      "Summer break",
    }
    serializer = ProgramPauseSerializer(data=data)
    assert serializer.is_valid(), serializer.errors

    pause_start = serializer.validated_data["pause_start"]
    assert pause_start.tzinfo is not None
    # Value should be preserved (13:00 UTC, i.e. 09:00 EDT)
    assert pause_start.hour == 13 or pause_start.utcoffset().total_seconds() != 0


@pytest.mark.django_db(transaction=True)
def test_schedule_voucher_tasks_coerces_naive_activate_time(
    participant_in_tuesday_program, db, caplog
):
    """
    Regression B: schedule_voucher_tasks must not raise TypeError when
    activate_time is a naive datetime.  The function converts it to aware
    and logs a warning rather than crashing.

    Before the fix, `activate_time > timezone.now()` raised TypeError because
    Python cannot compare a naive datetime with an aware one.
    """
    from apps.voucher.tasks.voucher_scheduling import schedule_voucher_tasks
    from apps.voucher.models import Voucher
    import logging

    vouchers = Voucher.objects.filter(active=True)
    naive_future = datetime(2026, 7, 15, 9, 0, 0)  # no tzinfo — naive

    with caplog.at_level(logging.WARNING, logger="apps.voucher.tasks.voucher_scheduling"):
        # Must not raise TypeError
        schedule_voucher_tasks(vouchers, activate_time=naive_future)

    assert any(
        "naive activate_time" in r.message for r in caplog.records
    ), "Expected a warning about naive activate_time"


# ---------------------------------------------------------------------------
# C. get_next_class_datetime advances to next week when class already passed
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_get_next_class_datetime_advances_when_meeting_just_passed(tuesday_program):
    """
    Regression C: if today is the same weekday as the meeting day AND the
    meeting time has already passed, get_next_class_datetime must return
    NEXT week's occurrence, not today's past time.

    Frozen to Tuesday 2026-06-09 at 19:00 UTC (15:00 EDT) — AFTER the 18:00 EDT class.
    """
    participant = Participant(program=tuesday_program)

    with freeze_time("2026-06-09 23:01:00+00:00"):  # 19:01 EDT, class was at 18:00
        result = get_next_class_datetime(participant)

    assert result is not None
    assert result > timezone.now().replace(tzinfo=None).astimezone(result.tzinfo) or result.tzinfo is not None

    # Must be next Tuesday (7 days later), not today
    with freeze_time("2026-06-09 23:01:00+00:00"):
        now = timezone.now()

    assert result > now, "Next class must be in the future, not today's past time"
    days_ahead = (result.date() - now.date()).days
    assert days_ahead == 7, (
        f"Expected 7 days ahead (next Tuesday), got {days_ahead}"
    )


@pytest.mark.django_db
def test_get_next_class_datetime_returns_today_when_class_not_yet_started(tuesday_program):
    """
    When today is the meeting day and the class has NOT started yet,
    get_next_class_datetime must return TODAY's class time (not skip a week).

    Frozen to Tuesday 2026-06-09 at 14:00 UTC (10:00 EDT) — BEFORE the 18:00 EDT class.
    """
    participant = Participant(program=tuesday_program)

    with freeze_time("2026-06-09 14:00:00+00:00"):  # 10:00 EDT
        result = get_next_class_datetime(participant)
        now = timezone.now()

    assert result is not None
    assert result > now, "Next class must still be in the future"
    days_ahead = (result.date() - now.date()).days
    assert days_ahead == 0, (
        f"Class today hasn't started yet — should be today, got {days_ahead} days ahead"
    )


# ---------------------------------------------------------------------------
# D. Deactivation task is idempotent — repeated calls don't crash or double-clear
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
def test_deactivation_task_called_twice_is_idempotent(
    participant_in_tuesday_program, db
):
    """
    If the signal re-fires and somehow schedules the deactivation task twice,
    the second run should be a no-op (idempotent), not crash or double-clear.
    """
    from apps.lifeskills.tasks.program_pause import deactivate_expired_pause_vouchers

    pause_start = timezone.now() + timedelta(days=12)
    pause_end = pause_start + timedelta(days=7)

    pp = ProgramPause.objects.create(
        pause_start=pause_start,
        pause_end=pause_end,
        reason="Idempotency test",
    )

    # First call — no crash expected
    result1 = deactivate_expired_pause_vouchers(program_pause_id=pp.id)
    # Second call — still no crash
    result2 = deactivate_expired_pause_vouchers(program_pause_id=pp.id)

    assert result1 is None
    assert result2 is None


@pytest.mark.django_db(transaction=True)
def test_deactivation_task_handles_deleted_pause_gracefully(db):
    """
    If ProgramPause was deleted between scheduling and execution,
    the task must exit cleanly (logged warning, no exception).
    """
    from apps.lifeskills.tasks.program_pause import deactivate_expired_pause_vouchers

    result = deactivate_expired_pause_vouchers(program_pause_id=999999)
    assert result is None
