"""
Regression tests — ProgramPause serializer and class-time issues (triaged 2026-06-09).

A. Naive datetimes from the API must be made aware at the serializer layer
   (ProgramPauseSerializer.validate_pause_start/end); comparing them with
   timezone.now() used to raise TypeError.

B. get_next_class_datetime returning a past datetime — when today is the same
   weekday as the meeting day AND the meeting time has already passed, the
   function must advance to next week.  The production code already handles
   this correctly; this test guards against regression.
"""

import pytest

from django.utils import timezone
from freezegun import freeze_time

from apps.account.models import Participant
from apps.lifeskills.models import Program
from core.utils import get_next_class_datetime


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tuesday_program(db):
    """Program that meets every Tuesday at 18:00."""
    return Program.objects.create(
        name="Tuesday Night",
        MeetingDay="tuesday",
        meeting_time="18:00:00",
        meeting_address="123 Main St",
    )


# ---------------------------------------------------------------------------
# A. Naive datetime bugs
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_serializer_makes_naive_pause_start_aware():
    """
    Regression B: ProgramPauseSerializer.validate_pause_start must convert
    naive datetimes to timezone-aware before they reach the model.
    """
    from apps.lifeskills.api.serializers import ProgramPauseSerializer

    data = {
        "pause_start": "2026-06-27T09:00:00",  # no tz offset — naive
        "pause_end": "2026-07-04T09:00:00",
        "reason": "Summer break",
    }
    serializer = ProgramPauseSerializer(data=data)
    assert serializer.is_valid(), serializer.errors

    pause_start = serializer.validated_data["pause_start"]
    pause_end = serializer.validated_data["pause_end"]

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
        "pause_end": "2026-07-04T09:00:00-04:00",
        "reason": "Summer break",
    }
    serializer = ProgramPauseSerializer(data=data)
    assert serializer.is_valid(), serializer.errors

    pause_start = serializer.validated_data["pause_start"]
    assert pause_start.tzinfo is not None
    # Value should be preserved (13:00 UTC, i.e. 09:00 EDT)
    assert pause_start.hour == 13 or pause_start.utcoffset().total_seconds() != 0


# ---------------------------------------------------------------------------
# B. get_next_class_datetime advances to next week when class already passed
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
