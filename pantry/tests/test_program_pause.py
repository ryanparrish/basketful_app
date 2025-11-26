import pytest
from freezegun import freeze_time
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from unittest import mock

from pantry.models import Participant, Voucher, ProgramPause, VoucherSetting, AccountBalance
from log.tasks.logs import update_voucher_flag

# ----------------------------
# Helpers
# ----------------------------
def _count_flagged_active(vouchers):
    return sum(1 for v in vouchers if v.active and v.program_pause_flag)


def _trigger_program_pause(start, end):
    """
    Create a ProgramPause and synchronously update vouchers.
    """
    pp = ProgramPause.objects.create(pause_start=start, pause_end=end, reason="Test Pause")
    update_voucher_flag(pp.id)
    return pp


# ----------------------------
# Tests
# ----------------------------
@freeze_time("2025-09-13 19:16:38")
@pytest.mark.django_db(transaction=True)
def test_signal_flags_two_active_vouchers(participant_with_vouchers, pause_duration):
    participant = participant_with_vouchers["participant"]
    account = participant_with_vouchers["account"]
    v1, v2, v3 = participant_with_vouchers["vouchers"]

    start = timezone.now()
    end = start + pause_duration

    # Patch apply_async so scheduled deactivation does not run in eager mode
    with mock.patch("food_orders.tasks.update_voucher_flag.apply_async"):
        _trigger_program_pause(start, end)

    # Refresh objects from DB to get task updates
    account.refresh_from_db()
    v1.refresh_from_db()
    v2.refresh_from_db()
    v3.refresh_from_db()

    flagged_active = _count_flagged_active([v1, v2, v3])
    assert flagged_active == 2
    assert v3.program_pause_flag is False


@freeze_time("2025-09-13 19:16:38")
@pytest.mark.django_db(transaction=True)
def test_signal_idempotency(participant_with_vouchers, pause_duration):
    participant = participant_with_vouchers["participant"]
    account = participant_with_vouchers["account"]
    v1, v2, v3 = participant_with_vouchers["vouchers"]

    start = timezone.now()
    end = start + pause_duration

    with mock.patch("food_orders.tasks.update_voucher_flag.apply_async"):
        pp = _trigger_program_pause(start, end)
        pp.save()
        pp.save()  # saving multiple times should not break flags

    v1.refresh_from_db()
    v2.refresh_from_db()
    v3.refresh_from_db()

    assert v1.program_pause_flag is True
    assert v2.program_pause_flag is True
    assert v3.program_pause_flag is False


@freeze_time("2025-09-13 19:16:38")
@pytest.mark.django_db(transaction=True)
def test_participant_with_single_voucher(db, pause_duration):
    participant = Participant.objects.create(name="P2", email="p2@test.com", active=True)
    account = AccountBalance.objects.get_or_create(participant=participant)[0]
    v = Voucher.objects.create(account=account, active=True)

    start = timezone.now()
    end = start + pause_duration

    with mock.patch("food_orders.tasks.update_voucher_flag.apply_async"):
        _trigger_program_pause(start, end)

    v.refresh_from_db()
    assert v.program_pause_flag is True


@freeze_time("2025-09-13 19:16:38")
@pytest.mark.django_db(transaction=True)
def test_voucher_balance_doubles_during_pause(participant_with_vouchers, pause_duration):
    participant = participant_with_vouchers["participant"]
    account = participant_with_vouchers["account"]

    # Add extra voucher if participant has adults
    for _ in range(max(1, getattr(participant, "adults", 1))):
        Voucher.objects.create(account=account, voucher_type="grocery", active=True)

    account.refresh_from_db()
    initial_balance = account.available_balance
    assert initial_balance > 0

    start = timezone.now()
    end = start + pause_duration

    with mock.patch("food_orders.tasks.update_voucher_flag.apply_async"):
        _trigger_program_pause(start, end)

    # refresh all vouchers
    for v in account.vouchers.all():
        v.refresh_from_db()
    account.refresh_from_db()
    balance_during_pause = account.available_balance

    assert balance_during_pause == initial_balance * 2
