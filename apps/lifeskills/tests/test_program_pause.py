import pytest
from freezegun import freeze_time
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone


from apps.account.models import Participant, AccountBalance
from apps.voucher.models import Voucher
from apps.lifeskills.models import ProgramPause, Program
from core.models import OrderWindowSettings


# ----------------------------
# Fixtures
# ----------------------------


@pytest.fixture
def participant_with_vouchers(db):
    """Create a participant with account and multiple vouchers."""
    # Create program with Wednesday meetings at 2pm
    program = Program.objects.create(
        name="Test Program",
        MeetingDay="wednesday",
        meeting_time="14:00:00",
        meeting_address="123 Test St"
    )
    participant = Participant.objects.create(
        name="Test Participant",
        email="test@example.com",
        program=program,
        active=True,
        adults=2,
        children=1,
    )
    account, _ = AccountBalance.objects.get_or_create(
        participant=participant,
        defaults={"base_balance": Decimal("100.0")}
    )
    
    # Ensure base_balance is set even if account already exists
    account.base_balance = Decimal("100.0")
    account.save()
    
    # Delete signal-created vouchers
    account.vouchers.all().delete()
    
    # Create three vouchers: two active, one inactive
    v1 = Voucher.objects.create(
        account=account,
        active=True,
        voucher_type="grocery",
        state="applied"
    )
    v2 = Voucher.objects.create(
        account=account,
        active=True,
        voucher_type="grocery",
        state="applied"
    )
    v3 = Voucher.objects.create(
        account=account,
        active=False,
        voucher_type="grocery",
        state="consumed"
    )
    
    # Ensure order window settings exist
    OrderWindowSettings.get_settings()
    
    return {
        "participant": participant,
        "account": account,
        "vouchers": [v1, v2, v3],
        "program": program
    }




# ----------------------------
# Tests
# ----------------------------


@freeze_time("2026-02-10 12:00:00")
@pytest.mark.django_db(transaction=True)
def test_balance_doubles_live_when_pause_enters_its_window(participant_with_vouchers):
    """
    #141: creating a pause in its double-week window doubles the balance
    immediately, with no voucher flagging or Celery task involved.
    """
    account = participant_with_vouchers["account"]
    account.refresh_from_db()
    initial_balance = account.available_balance
    assert initial_balance > 0

    pause_start = timezone.now() + timedelta(days=12)
    ProgramPause.objects.create(
        pause_start=pause_start,
        pause_end=pause_start + timedelta(days=7),
        reason="Week Off",
    )

    account.refresh_from_db()
    assert account.available_balance == initial_balance * 2


@pytest.mark.django_db(transaction=True) 
def test_multiplier_calculation_utility():
    """Test the new class method for calculating multiplier."""
    now = timezone.now()
    
    # Short pause (7 days) should give multiplier 2
    start = now + timedelta(days=12)
    end = start + timedelta(days=7)
    assert ProgramPause.calculate_multiplier_for_duration(start, end) == 2
    
    # Extended pause (14 days) should give multiplier 3
    end_extended = start + timedelta(days=14)
    assert ProgramPause.calculate_multiplier_for_duration(start, end_extended) == 3
    
    # Edge case: exactly 14 days
    end_exact = start + timedelta(days=13)  # days + 1 in calc = 14
    assert ProgramPause.calculate_multiplier_for_duration(start, end_exact) == 3
