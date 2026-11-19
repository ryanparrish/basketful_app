"""
#121: cleaning up after an ended pause must not clear the voucher flags of a
different pause that is in its double-week window (10-14 days before its
start). Vouchers don't record which pause flagged them, so every reset path
skips the reset while any live pause is in that window.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.account.models import AccountBalance, Participant
from apps.lifeskills.models import Program, ProgramPause
from apps.lifeskills.tasks.program_pause import (
    cleanup_expired_pause_flags,
    final_cleanup_after_pause_end,
)
from apps.lifeskills.utils import set_voucher_pause_state
from apps.voucher.models import Voucher
from core.models import OrderWindowSettings


@pytest.fixture
def flagged_voucher_ids(db):
    """Two active grocery vouchers for one participant."""
    program = Program.objects.create(
        name="Tuesday Spanish",
        MeetingDay="tuesday",
        meeting_time="14:00:00",
        meeting_address="123 Test St",
    )
    participant = Participant.objects.create(
        name="Pause Participant",
        email="pause@example.com",
        program=program,
        active=True,
        adults=2,
        children=1,
    )
    account, _ = AccountBalance.objects.get_or_create(
        participant=participant, defaults={"base_balance": Decimal("100.0")}
    )
    account.vouchers.all().delete()
    vouchers = [
        Voucher.objects.create(account=account, active=True, voucher_type="grocery", state="applied")
        for _ in range(2)
    ]
    OrderWindowSettings.get_settings()
    return [voucher.id for voucher in vouchers]


def create_ended_pause():
    now = timezone.now()
    return ProgramPause.objects.create(
        pause_start=now - timedelta(days=20),
        pause_end=now - timedelta(days=13),
        reason="Ended pause",
    )


def create_pause_in_double_week():
    """A one-week pause starting in 12 days: inside its 10-14 day window."""
    now = timezone.now()
    pause = ProgramPause.objects.create(
        pause_start=now + timedelta(days=12),
        pause_end=now + timedelta(days=19),
        reason="Upcoming pause",
    )
    assert pause.is_active_gate
    return pause


def flag_state(voucher_ids):
    return sorted(
        Voucher.objects.filter(id__in=voucher_ids).values_list("program_pause_flag", "multiplier")
    )


def doubled(voucher_ids):
    set_voucher_pause_state(voucher_ids, activate=True, multiplier=2)


@pytest.mark.django_db
class TestDailyCleanupKeepsLivePauseFlags:

    def test_flags_survive_when_another_pause_is_in_its_double_week(self, flagged_voucher_ids):
        ended = create_ended_pause()
        create_pause_in_double_week()
        doubled(flagged_voucher_ids)

        cleanup_expired_pause_flags()

        assert flag_state(flagged_voucher_ids) == [(True, 2), (True, 2)]
        ended.refresh_from_db()
        assert ended.archived is True

    def test_stale_flags_are_still_cleared_when_no_pause_is_in_its_double_week(self, flagged_voucher_ids):
        create_ended_pause()
        doubled(flagged_voucher_ids)

        cleanup_expired_pause_flags()

        assert flag_state(flagged_voucher_ids) == [(False, 1), (False, 1)]


@pytest.mark.django_db
class TestOtherResetPathsKeepLivePauseFlags:

    def test_final_cleanup(self, flagged_voucher_ids):
        ended = create_ended_pause()
        create_pause_in_double_week()
        doubled(flagged_voucher_ids)

        final_cleanup_after_pause_end(program_pause_id=ended.id)

        assert flag_state(flagged_voucher_ids) == [(True, 2), (True, 2)]
        ended.refresh_from_db()
        assert ended.archived is True

    def test_archive(self, flagged_voucher_ids):
        ended = create_ended_pause()
        create_pause_in_double_week()
        doubled(flagged_voucher_ids)

        ProgramPause.objects.all_pauses().get(pk=ended.pk).archive()

        assert flag_state(flagged_voucher_ids) == [(True, 2), (True, 2)]
        ended.refresh_from_db()
        assert ended.archived is True
