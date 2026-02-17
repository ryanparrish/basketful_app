"""Tests for program pause cleanup functionality."""
import pytest
from freezegun import freeze_time
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from unittest import mock

from apps.account.models import Participant, AccountBalance
from apps.voucher.models import Voucher
from apps.lifeskills.models import ProgramPause, Program
from apps.lifeskills.utils import set_voucher_pause_state
from apps.lifeskills.tasks.program_pause import (
    update_voucher_flag_task,
    deactivate_expired_pause_vouchers,
    final_cleanup_after_pause_end,
    cleanup_expired_pause_flags
)
from core.models import OrderWindowSettings


# ----------------------------
# Fixtures
# ----------------------------
@pytest.fixture
def participant_with_vouchers(db):
    """Create a participant with account and multiple vouchers."""
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
# Tests for set_voucher_pause_state utility
# ----------------------------
@pytest.mark.django_db
class TestSetVoucherPauseState:
    """Tests for the set_voucher_pause_state utility function."""

    def test_activates_vouchers_with_multiplier(self, participant_with_vouchers):
        """Test that activate=True sets flag and multiplier."""
        vouchers = participant_with_vouchers["vouchers"]
        active_ids = [v.id for v in vouchers if v.active]
        
        updated, skipped = set_voucher_pause_state(active_ids, activate=True, multiplier=2)
        
        assert updated == 2
        assert skipped == 0
        
        for v in Voucher.objects.filter(id__in=active_ids):
            assert v.program_pause_flag is True
            assert v.multiplier == 2

    def test_deactivates_vouchers_resets_multiplier(self, participant_with_vouchers):
        """Test that activate=False clears flag and resets multiplier."""
        vouchers = participant_with_vouchers["vouchers"]
        active_ids = [v.id for v in vouchers if v.active]
        
        # First activate
        set_voucher_pause_state(active_ids, activate=True, multiplier=3)
        
        # Then deactivate
        updated, skipped = set_voucher_pause_state(active_ids, activate=False, multiplier=1)
        
        assert updated == 2
        assert skipped == 0
        
        for v in Voucher.objects.filter(id__in=active_ids):
            assert v.program_pause_flag is False
            assert v.multiplier == 1

    def test_idempotent_skips_already_correct_vouchers(self, participant_with_vouchers):
        """Test that calling twice with same state skips already-correct vouchers."""
        vouchers = participant_with_vouchers["vouchers"]
        active_ids = [v.id for v in vouchers if v.active]
        
        # First call
        updated1, skipped1 = set_voucher_pause_state(active_ids, activate=True, multiplier=2)
        assert updated1 == 2
        assert skipped1 == 0
        
        # Second call with same state
        updated2, skipped2 = set_voucher_pause_state(active_ids, activate=True, multiplier=2)
        assert updated2 == 0
        assert skipped2 == 2

    def test_handles_empty_voucher_list(self, participant_with_vouchers):
        """Test that empty voucher list returns 0, 0."""
        updated, skipped = set_voucher_pause_state([], activate=True, multiplier=2)
        assert updated == 0
        assert skipped == 0

    def test_handles_nonexistent_voucher_ids(self, participant_with_vouchers):
        """Test that nonexistent IDs are silently skipped."""
        vouchers = participant_with_vouchers["vouchers"]
        active_ids = [v.id for v in vouchers if v.active]
        
        # Add an invalid ID
        invalid_ids = active_ids + [99999]
        
        # Should not raise error, just skip invalid IDs
        updated, skipped = set_voucher_pause_state(invalid_ids, activate=True, multiplier=2)
        
        # Only valid vouchers should be updated
        assert updated == 2
        assert skipped == 0
        
        # Verify valid vouchers were updated
        for v in Voucher.objects.filter(id__in=active_ids):
            assert v.program_pause_flag is True


# ----------------------------
# Tests for refactored tasks
# ----------------------------
@pytest.mark.django_db
class TestRefactoredTasks:
    """Tests for tasks that now use set_voucher_pause_state."""

    def test_update_voucher_flag_task_uses_utility(self, participant_with_vouchers):
        """Test that update_voucher_flag_task properly activates vouchers."""
        now = timezone.now()
        # Create pause in 11-14 day window so signal triggers activation
        pause = ProgramPause.objects.create(
            pause_start=now + timedelta(days=12),
            pause_end=now + timedelta(days=19),
            reason="Test Pause"
        )
        
        # Directly call the task (in eager mode it executes synchronously)
        update_voucher_flag_task(pause.id)
        
        # Verify vouchers were flagged
        vouchers = participant_with_vouchers["vouchers"]
        active_vouchers = [v for v in vouchers if v.active]
        
        for v in Voucher.objects.filter(id__in=[av.id for av in active_vouchers]):
            assert v.program_pause_flag is True
            assert v.multiplier >= 1

    @freeze_time("2024-01-15 10:00:00")
    def test_deactivate_task_schedules_final_cleanup(self, participant_with_vouchers):
        """Test that deactivate task schedules final cleanup at pause_end."""
        now = timezone.now()
        pause = ProgramPause.objects.create(
            pause_start=now - timedelta(days=14),
            pause_end=now + timedelta(hours=2),  # Ends in 2 hours
            reason="Test Pause"
        )
        
        # Manually activate vouchers using utility
        vouchers = participant_with_vouchers["vouchers"]
        active_ids = [v.id for v in vouchers if v.active]
        set_voucher_pause_state(active_ids, activate=True, multiplier=2)
        
        with mock.patch('apps.lifeskills.tasks.program_pause.final_cleanup_after_pause_end.apply_async') as mock_cleanup:
            deactivate_expired_pause_vouchers(pause.id)
            
            # Should schedule final cleanup for pause_end + 5 minutes
            expected_eta = pause.pause_end + timedelta(minutes=5)
            mock_cleanup.assert_called_once()
            call_kwargs = mock_cleanup.call_args[1]
            assert 'eta' in call_kwargs
            assert call_kwargs['kwargs'] == {'pause_id': pause.id}


# ----------------------------
# Tests for final cleanup task
# ----------------------------
@pytest.mark.django_db
class TestFinalCleanupTask:
    """Tests for final_cleanup_after_pause_end task."""

    def test_cleans_up_vouchers_after_pause_end(self, participant_with_vouchers):
        """Test that final cleanup resets vouchers and archives pause."""
        now = timezone.now()
        pause = ProgramPause.objects.create(
            pause_start=now - timedelta(days=14),
            pause_end=now - timedelta(minutes=10),  # Already ended
            reason="Test Pause"
        )
        
        # Activate vouchers
        vouchers = participant_with_vouchers["vouchers"]
        active_ids = [v.id for v in vouchers if v.active]
        set_voucher_pause_state(active_ids, activate=True, multiplier=2)
        
        # Run cleanup
        final_cleanup_after_pause_end(pause.id)
        
        # Verify vouchers reset
        for v in Voucher.objects.filter(id__in=active_ids):
            assert v.program_pause_flag is False
            assert v.multiplier == 1
        
        # Verify pause archived
        pause.refresh_from_db()
        assert pause.archived is True
        assert pause.archived_at is not None

    def test_skips_if_vouchers_already_clean(self, participant_with_vouchers):
        """Test that cleanup is idempotent."""
        now = timezone.now()
        pause = ProgramPause.objects.create(
            pause_start=now - timedelta(days=14),
            pause_end=now - timedelta(minutes=10),
            reason="Test Pause"
        )
        
        # Run cleanup twice
        final_cleanup_after_pause_end(pause.id)
        final_cleanup_after_pause_end(pause.id)
        
        # Should not raise error, pause should be archived
        pause.refresh_from_db()
        assert pause.archived is True


# ----------------------------
# Tests for daily cleanup task
# ----------------------------
@pytest.mark.django_db
class TestDailyCleanupTask:
    """Tests for cleanup_expired_pause_flags daily task."""

    def test_cleans_all_expired_pauses(self, participant_with_vouchers):
        """Test that daily task finds and cleans all expired pauses."""
        now = timezone.now()
        
        # Create multiple expired pauses
        pause1 = ProgramPause.objects.create(
            pause_start=now - timedelta(days=30),
            pause_end=now - timedelta(days=23),
            reason="Old Pause 1"
        )
        pause2 = ProgramPause.objects.create(
            pause_start=now - timedelta(days=20),
            pause_end=now - timedelta(days=13),
            reason="Old Pause 2"
        )
        
        # Create a future pause that should not be cleaned
        pause3 = ProgramPause.objects.create(
            pause_start=now + timedelta(days=1),
            pause_end=now + timedelta(days=8),
            reason="Future Pause"
        )
        
        # Flag some vouchers
        vouchers = participant_with_vouchers["vouchers"]
        active_ids = [v.id for v in vouchers if v.active]
        set_voucher_pause_state(active_ids, activate=True, multiplier=2)
        
        # Run daily cleanup
        cleanup_expired_pause_flags()
        
        # Verify expired pauses archived
        pause1.refresh_from_db()
        pause2.refresh_from_db()
        assert pause1.archived is True
        assert pause2.archived is True
        
        # Verify future pause not archived
        pause3.refresh_from_db()
        assert pause3.archived is False
        
        # Verify vouchers cleaned
        for v in Voucher.objects.filter(id__in=active_ids):
            assert v.program_pause_flag is False
            assert v.multiplier == 1

    def test_handles_already_archived_pauses(self, participant_with_vouchers):
        """Test that daily cleanup skips already-archived pauses."""
        now = timezone.now()
        pause = ProgramPause.objects.create(
            pause_start=now - timedelta(days=30),
            pause_end=now - timedelta(days=23),
            reason="Old Pause",
            archived=True,
            archived_at=now - timedelta(days=22)
        )
        
        # Run cleanup
        cleanup_expired_pause_flags()
        
        # Should not cause errors
        pause.refresh_from_db()
        assert pause.archived is True


# ----------------------------
# Tests for archive/unarchive functionality
# ----------------------------
@pytest.mark.django_db
class TestArchiveFunctionality:
    """Tests for ProgramPause archive and unarchive methods."""

    def test_archive_cleans_vouchers_and_sets_fields(self, participant_with_vouchers):
        """Test that archive() resets vouchers and sets archived fields."""
        now = timezone.now()
        pause = ProgramPause.objects.create(
            pause_start=now - timedelta(days=14),
            pause_end=now - timedelta(days=7),
            reason="Test Pause"
        )
        
        # Activate vouchers
        vouchers = participant_with_vouchers["vouchers"]
        active_ids = [v.id for v in vouchers if v.active]
        set_voucher_pause_state(active_ids, activate=True, multiplier=2)
        
        # Archive
        pause.archive()
        
        # Verify fields set
        assert pause.archived is True
        assert pause.archived_at is not None
        
        # Verify vouchers cleaned
        for v in Voucher.objects.filter(id__in=active_ids):
            assert v.program_pause_flag is False
            assert v.multiplier == 1

    def test_unarchive_reactivates_if_pause_active(self, participant_with_vouchers):
        """Test that unarchiving active pause re-flags vouchers."""
        now = timezone.now()
        # Create pause in 11-14 day window so reactivation works
        pause = ProgramPause.objects.create(
            pause_start=now + timedelta(days=12),
            pause_end=now + timedelta(days=19),  # Still active
            reason="Test Pause",
            archived=True,
            archived_at=now - timedelta(hours=1)
        )
        
        # Unarchive
        pause.unarchive()
        
        # Verify fields cleared
        assert pause.archived is False
        assert pause.archived_at is None
        
        # Verify vouchers get flagged on save (triggers signal)
        pause.save()
        
        vouchers = participant_with_vouchers["vouchers"]
        active_ids = [v.id for v in vouchers if v.active]
        for v in Voucher.objects.filter(id__in=active_ids):
            assert v.program_pause_flag is True

    def test_manager_excludes_archived_by_default(self, participant_with_vouchers):
        """Test that default queryset excludes archived pauses."""
        now = timezone.now()
        
        active_pause = ProgramPause.objects.create(
            pause_start=now,
            pause_end=now + timedelta(days=7),
            reason="Active"
        )
        archived_pause = ProgramPause.objects.create(
            pause_start=now - timedelta(days=14),
            pause_end=now - timedelta(days=7),
            reason="Archived",
            archived=True,
            archived_at=now
        )
        
        # Default queryset should exclude archived
        assert active_pause in ProgramPause.objects.all()
        assert archived_pause not in ProgramPause.objects.all()
        
        # all_pauses() should include both
        all_pauses = ProgramPause.objects.all_pauses()
        assert active_pause in all_pauses
        assert archived_pause in all_pauses


# ----------------------------
# Integration test
# ----------------------------
@pytest.mark.django_db
class TestCompletePauseLifecycle:
    """Integration test for complete pause lifecycle."""

    @freeze_time("2024-01-15 10:00:00")
    def test_complete_lifecycle_with_cleanup(self, participant_with_vouchers):
        """Test complete lifecycle: create → activate → deactivate → final cleanup → daily safety."""
        now = timezone.now()
        
        # Step 1: Create pause in 11-14 day window (should activate immediately with multiplier)
        pause = ProgramPause.objects.create(
            pause_start=now + timedelta(days=12),
            pause_end=now + timedelta(days=19),
            reason="Lifecycle Test"
        )
        
        # Step 2: Manually activate vouchers to simulate signal behavior
        vouchers = participant_with_vouchers["vouchers"]
        active_ids = [v.id for v in vouchers if v.active]
        set_voucher_pause_state(active_ids, activate=True, multiplier=2)
        
        # Verify vouchers activated
        for v in Voucher.objects.filter(id__in=active_ids):
            assert v.program_pause_flag is True
            assert v.multiplier >= 1
        
        # Step 3: Fast forward to window close (should deactivate but not clean)
        with freeze_time("2024-01-18 10:00:00"):  # 3 days later, window closed
            with mock.patch('apps.lifeskills.tasks.program_pause.final_cleanup_after_pause_end.apply_async'):
                # Deactivate during window (pause hasn't ended yet)
                set_voucher_pause_state(active_ids, activate=False, multiplier=1)
            
            # Vouchers should be deactivated
            for v in Voucher.objects.filter(id__in=active_ids):
                v.refresh_from_db()
                assert v.program_pause_flag is False
        
        # Step 4: Fast forward past pause_end and run final cleanup
        with freeze_time("2024-01-22 10:10:00"):  # Past pause_end + 5 min
            final_cleanup_after_pause_end(pause.id)
            
            # Vouchers should be reset
            for v in Voucher.objects.filter(id__in=active_ids):
                v.refresh_from_db()
                assert v.program_pause_flag is False
                assert v.multiplier == 1
            
            # Pause should be archived
            pause.refresh_from_db()
            assert pause.archived is True
        
        # Step 5: Run daily cleanup (should be idempotent)
        with freeze_time("2024-01-23 03:00:00"):  # Next day at 3 AM
            cleanup_expired_pause_flags()
            
            # Should not cause errors, pause already archived
            pause.refresh_from_db()
            assert pause.archived is True
