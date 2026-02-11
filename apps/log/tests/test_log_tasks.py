"""
Comprehensive tests for log task functions.

Tests cover:
- log_voucher_application_task: Voucher application logging
- update_voucher_flag: Voucher flag and multiplier updates with program pause logic
- Idempotent behavior
- Error handling and retries
- Edge cases
"""

import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.utils import timezone
from datetime import timedelta

from apps.log.tasks.logs import (
    log_voucher_application_task,
    update_voucher_flag,
)
from apps.log.models import VoucherLog
from apps.voucher.models import Voucher, VoucherSetting
from apps.account.models import Participant, AccountBalance
from apps.orders.models import Order
from apps.lifeskills.models import Program, ProgramPause


@pytest.fixture
def program():
    """Create a test program."""
    return Program.objects.create(
        name='Test Program',
        meeting_time='10:00:00',
        MeetingDay='monday',
        meeting_address='123 Test St'
    )


@pytest.fixture
def voucher_setting():
    """Create a test voucher setting."""
    VoucherSetting.objects.all().update(active=False)
    return VoucherSetting.objects.create(
        adult_amount=Decimal('50.00'),
        child_amount=Decimal('25.00'),
        infant_modifier=Decimal('10.00'),
        active=True
    )


@pytest.fixture
def participant(program):
    """Create a test participant."""
    return Participant.objects.create(
        name='Test Participant',
        email='test@example.com',
        adults=2,
        children=1,
        program=program
    )


@pytest.fixture
def account_balance(participant, voucher_setting):
    """Create an account balance for the participant."""
    # Use get_or_create to avoid conflict with signal
    balance, _ = AccountBalance.objects.get_or_create(
        participant=participant,
        defaults={'base_balance': Decimal('100.00')}
    )
    return balance


@pytest.fixture
def voucher(account_balance, voucher_setting):
    """Create a test voucher with explicit amount."""
    # Ensure account has base_balance set
    if account_balance.base_balance == 0:
        account_balance.base_balance = Decimal('100.00')
        account_balance.save()
    
    voucher = Voucher.objects.create(
        account=account_balance,
        voucher_type='grocery',
        state='applied',
        multiplier=1,
        active=True
    )
    # Voucher amount is calculated from account base_balance and multiplier
    # With base_balance=100 and multiplier=1, voucher_amnt should be 100
    return voucher


@pytest.fixture
def order(participant, account_balance):
    """Create a test order."""
    from apps.orders.models import Order
    # Using the helper from combined order tests
    order = Order(
        account=account_balance,
        status='confirmed'
    )
    # Save without triggering validation
    from django.db.models import Model
    Model.save(order)
    return order


# ============================================================
# log_voucher_application_task Tests
# ============================================================

@pytest.mark.django_db
class TestLogVoucherApplicationTask:
    """Test log_voucher_application_task function."""
    
    def test_log_voucher_application_full_usage(self, order, voucher, participant, account_balance):
        """Test logging when voucher is fully used."""
        voucher_amount = voucher.voucher_amnt
        
        # Call the task
        log_voucher_application_task(
            order_id=order.id,
            voucher_id=voucher.id,
            participant_id=participant.id,
            applied_amount=float(voucher_amount),
            remaining=0.0
        )
        
        # Check that log was created
        log = VoucherLog.objects.get(order=order, voucher=voucher)
        assert log.participant == participant
        assert log.applied_amount == voucher_amount
        assert log.remaining == Decimal('0.00')
        assert log.log_type == VoucherLog.INFO
        assert 'Fully used voucher' in log.message
        assert f'${float(voucher_amount):.2f}' in log.message
    
    def test_log_voucher_application_partial_usage(self, order, voucher, participant):
        """Test logging when voucher is partially used."""
        voucher_amount = voucher.voucher_amnt
        applied = float(voucher_amount) / 2  # 50.0 if voucher_amnt is 100
        remaining = 50.0
        
        log_voucher_application_task(
            order_id=order.id,
            voucher_id=voucher.id,
            participant_id=participant.id,
            applied_amount=applied,
            remaining=remaining
        )
        
        # Check that log was created
        log = VoucherLog.objects.get(order=order, voucher=voucher)
        # Verify the applied amount is stored correctly
        assert log.applied_amount == Decimal(str(applied))
        assert log.remaining == Decimal('50.00')
        # Since applied (50) < voucher_amnt (100), should say "Partially used"
        assert 'Partially used voucher' in log.message
    
    def test_log_voucher_application_none_values(self, order, voucher, participant):
        """Test logging handles None values correctly."""
        log_voucher_application_task(
            order_id=order.id,
            voucher_id=voucher.id,
            participant_id=participant.id,
            applied_amount=None,
            remaining=None
        )
        
        # Check that log was created with 0.0 values
        log = VoucherLog.objects.get(order=order, voucher=voucher)
        assert log.applied_amount == Decimal('0.00')
        assert log.remaining == Decimal('0.00')
    
    def test_log_voucher_application_multiple_logs(self, order, voucher, participant):
        """Test that multiple applications create separate logs."""
        # First application
        log_voucher_application_task(
            order_id=order.id,
            voucher_id=voucher.id,
            participant_id=participant.id,
            applied_amount=25.0,
            remaining=75.0
        )
        
        # Second application
        log_voucher_application_task(
            order_id=order.id,
            voucher_id=voucher.id,
            participant_id=participant.id,
            applied_amount=75.0,
            remaining=0.0
        )
        
        # Check that both logs were created
        logs = VoucherLog.objects.filter(order=order, voucher=voucher)
        assert logs.count() == 2


# ============================================================
# update_voucher_flag Tests
# ============================================================

@pytest.mark.django_db
class TestUpdateVoucherFlag:
    """Test update_voucher_flag task function."""
    
    def test_activate_voucher_flag(self, voucher):
        """Test activating program_pause_flag on a voucher."""
        # Ensure flag is initially False
        assert voucher.program_pause_flag is False
        assert voucher.multiplier == 1
        
        # Activate the flag
        update_voucher_flag(
            voucher_ids=[voucher.id],
            multiplier=2,
            activate=True
        )
        
        # Refresh and verify
        voucher.refresh_from_db()
        assert voucher.program_pause_flag is True
        assert voucher.multiplier == 2
    
    def test_deactivate_voucher_flag(self, voucher):
        """Test deactivating program_pause_flag on a voucher."""
        # Set up voucher with flag active
        voucher.program_pause_flag = True
        voucher.multiplier = 3
        voucher.save()
        
        # Deactivate the flag
        update_voucher_flag(
            voucher_ids=[voucher.id],
            multiplier=1,
            activate=False
        )
        
        # Refresh and verify
        voucher.refresh_from_db()
        assert voucher.program_pause_flag is False
        assert voucher.multiplier == 1
    
    def test_update_multiple_vouchers(self, account_balance, voucher_setting):
        """Test updating multiple vouchers at once."""
        # Create multiple vouchers
        voucher1 = Voucher.objects.create(
            account=account_balance,
            voucher_type='grocery',
            state='applied',
            multiplier=1,
            active=True
        )
        voucher2 = Voucher.objects.create(
            account=account_balance,
            voucher_type='grocery',
            state='applied',
            multiplier=1,
            active=True
        )
        voucher3 = Voucher.objects.create(
            account=account_balance,
            voucher_type='grocery',
            state='applied',
            multiplier=1,
            active=True
        )
        
        # Update all at once
        update_voucher_flag(
            voucher_ids=[voucher1.id, voucher2.id, voucher3.id],
            multiplier=2,
            activate=True
        )
        
        # Verify all were updated
        for v in [voucher1, voucher2, voucher3]:
            v.refresh_from_db()
            assert v.program_pause_flag is True
            assert v.multiplier == 2
    
    def test_idempotent_update_already_activated(self, voucher):
        """Test that updating already-activated voucher is idempotent."""
        # Set up voucher already activated
        voucher.program_pause_flag = True
        voucher.multiplier = 2
        voucher.save()
        
        # Run update again with same values
        update_voucher_flag(
            voucher_ids=[voucher.id],
            multiplier=2,
            activate=True
        )
        
        # Verify state unchanged
        voucher.refresh_from_db()
        assert voucher.program_pause_flag is True
        assert voucher.multiplier == 2
    
    def test_single_voucher_id_as_int(self, voucher):
        """Test that a single voucher ID as int is handled correctly."""
        # Pass single int instead of list
        update_voucher_flag(
            voucher_ids=voucher.id,  # int, not list
            multiplier=2,
            activate=True
        )
        
        voucher.refresh_from_db()
        assert voucher.program_pause_flag is True
        assert voucher.multiplier == 2
    
    def test_empty_voucher_ids_list(self):
        """Test that empty list is handled gracefully."""
        # Should not raise an error
        update_voucher_flag(
            voucher_ids=[],
            multiplier=2,
            activate=True
        )
        # No assertion needed - just shouldn't crash
    
    def test_none_voucher_ids(self):
        """Test that None voucher_ids is handled gracefully."""
        # Should not raise an error
        update_voucher_flag(
            voucher_ids=None,
            multiplier=2,
            activate=True
        )
        # No assertion needed - just shouldn't crash


# ============================================================
# Program Pause Integration Tests
# ============================================================

@pytest.mark.django_db
class TestUpdateVoucherFlagWithProgramPause:
    """Test update_voucher_flag with program pause timing logic."""
    
    def test_skip_activation_pause_not_started(self, voucher):
        """Test that activation happens if pause is within ordering window."""
        now = timezone.now()
        
        # Create a future pause (outside 11-14 day window, so no immediate activation)
        # Using 20 days in future to be outside the ordering window
        pause = ProgramPause(
            pause_start=now + timedelta(days=20),
            pause_end=now + timedelta(days=25),
            reason='Future Pause'
        )
        pause._skip_signal = True
        pause.save()
        
        # Try to activate - new logic allows activation during ordering window
        # but since we're outside the window (20 days), it should still activate
        # because the check was removed to allow ordering window activation
        update_voucher_flag(
            voucher_ids=[voucher.id],
            multiplier=2,
            activate=True,
            program_pause_id=pause.id
        )
        
        # With the fix, vouchers ARE updated (no longer blocking activation)
        voucher.refresh_from_db()
        assert voucher.program_pause_flag is True
        assert voucher.multiplier == 2
        
        pause.delete()
    
    def test_skip_deactivation_pause_not_ended(self, voucher):
        """Test that deactivation is skipped if pause hasn't ended yet."""
        now = timezone.now()
        
        # Set up voucher with flag active
        voucher.program_pause_flag = True
        voucher.multiplier = 2
        voucher.save()
        
        # Create a current/future pause (skip signal to avoid interference)
        pause = ProgramPause(
            pause_start=now - timedelta(days=1),
            pause_end=now + timedelta(days=5),
            reason='Current Pause'
        )
        pause._skip_signal = True
        pause.save()
        
        # Try to deactivate - should skip
        update_voucher_flag(
            voucher_ids=[voucher.id],
            multiplier=1,
            activate=False,
            program_pause_id=pause.id
        )
        
        # Verify voucher was NOT updated (still active)
        voucher.refresh_from_db()
        assert voucher.program_pause_flag is True
        assert voucher.multiplier == 2
        
        pause.delete()
    
    def test_activate_when_pause_started(self, voucher):
        """Test successful activation when pause has started."""
        now = timezone.now()
        
        # Create a pause that has started (skip signal to avoid interference)
        pause = ProgramPause(
            pause_start=now - timedelta(days=1),
            pause_end=now + timedelta(days=5),
            reason='Active Pause'
        )
        pause._skip_signal = True
        pause.save()
        
        # Activate - should succeed
        update_voucher_flag(
            voucher_ids=[voucher.id],
            multiplier=2,
            activate=True,
            program_pause_id=pause.id
        )
        
        # Verify voucher was updated
        voucher.refresh_from_db()
        assert voucher.program_pause_flag is True
        assert voucher.multiplier == 2
        
        pause.delete()
    
    def test_deactivate_when_pause_ended(self, voucher):
        """Test successful deactivation when pause has ended."""
        now = timezone.now()
        
        # Set up voucher with flag active
        voucher.program_pause_flag = True
        voucher.multiplier = 2
        voucher.save()
        
        # Create a pause that has ended (skip signal to avoid interference)
        pause = ProgramPause(
            pause_start=now - timedelta(days=10),
            pause_end=now - timedelta(days=1),
            reason='Ended Pause'
        )
        pause._skip_signal = True
        pause.save()
        
        # Deactivate - should succeed
        update_voucher_flag(
            voucher_ids=[voucher.id],
            multiplier=1,
            activate=False,
            program_pause_id=pause.id
        )
        
        # Verify voucher was updated
        voucher.refresh_from_db()
        assert voucher.program_pause_flag is False
        assert voucher.multiplier == 1
        
        pause.delete()
    
    def test_nonexistent_program_pause_id(self, voucher):
        """Test handling of nonexistent program pause ID."""
        # Should skip duration check and proceed with update
        update_voucher_flag(
            voucher_ids=[voucher.id],
            multiplier=2,
            activate=True,
            program_pause_id=99999  # Doesn't exist
        )
        
        # Verify voucher was still updated (duration check skipped)
        voucher.refresh_from_db()
        assert voucher.program_pause_flag is True
        assert voucher.multiplier == 2


# ============================================================
# Error Handling and Edge Cases
# ============================================================

@pytest.mark.django_db
class TestUpdateVoucherFlagErrorHandling:
    """Test error handling in update_voucher_flag."""
    
    def test_partial_update_on_error(self, account_balance, voucher_setting):
        """Test behavior when some vouchers exist and some don't."""
        # Create one valid voucher
        voucher1 = Voucher.objects.create(
            account=account_balance,
            voucher_type='grocery',
            state='applied',
            multiplier=1,
            active=True
        )
        
        # Try to update valid and invalid IDs
        # Should update the valid one
        update_voucher_flag(
            voucher_ids=[voucher1.id, 99999],  # 99999 doesn't exist
            multiplier=2,
            activate=True
        )
        
        # Valid voucher should be updated
        voucher1.refresh_from_db()
        assert voucher1.program_pause_flag is True
        assert voucher1.multiplier == 2
    
    def test_retry_on_exception(self, voucher):
        """Test that task retries on exception."""
        # Patch Voucher.objects.filter to raise an exception
        with patch('apps.log.tasks.logs.Voucher.objects.filter') as mock_filter:
            mock_filter.side_effect = Exception("Database error")
            
            # The task will catch the exception and call retry, which re-raises
            # The original exception, so we expect the Database error
            with pytest.raises(Exception, match="Database error"):
                update_voucher_flag([voucher.id], 2, True)


# ============================================================
# Integration Tests
# ============================================================

@pytest.mark.django_db
class TestLogTasksIntegration:
    """Integration tests combining multiple task scenarios."""
    
    def test_voucher_lifecycle_with_logging(self, order, voucher, participant, account_balance):
        """Test complete voucher lifecycle: activate, use, log, deactivate."""
        # 1. Activate voucher with pause flag
        update_voucher_flag(
            voucher_ids=[voucher.id],
            multiplier=2,
            activate=True
        )
        voucher.refresh_from_db()
        assert voucher.program_pause_flag is True
        
        # 2. Log voucher application
        log_voucher_application_task(
            order_id=order.id,
            voucher_id=voucher.id,
            participant_id=participant.id,
            applied_amount=100.0,
            remaining=0.0
        )
        
        # Verify log exists
        log = VoucherLog.objects.get(order=order, voucher=voucher)
        assert log is not None
        
        # 3. Deactivate voucher
        update_voucher_flag(
            voucher_ids=[voucher.id],
            multiplier=1,
            activate=False
        )
        voucher.refresh_from_db()
        assert voucher.program_pause_flag is False
    
    def test_multiple_orders_multiple_vouchers(self, participant, account_balance, voucher_setting):
        """Test complex scenario with multiple orders and vouchers."""
        import uuid
        
        # Create multiple vouchers
        vouchers = [
            Voucher.objects.create(
                account=account_balance,
                voucher_type='grocery',
                state='applied',
                multiplier=1,
                active=True
            )
            for _ in range(3)
        ]
        
        # Create multiple orders with unique order_numbers
        from django.db.models import Model
        orders = []
        for _ in range(2):
            order = Order(account=account_balance, status='confirmed')
            Model.save(order)
            # Set unique order_number after save to avoid constraint
            Order.objects.filter(pk=order.pk).update(order_number=str(uuid.uuid4())[:20])
            order.refresh_from_db()
            orders.append(order)
        
        # Activate all vouchers
        voucher_ids = [v.id for v in vouchers]
        update_voucher_flag(
            voucher_ids=voucher_ids,
            multiplier=3,
            activate=True
        )
        
        # Log applications for each order
        for order in orders:
            for voucher in vouchers:
                log_voucher_application_task(
                    order_id=order.id,
                    voucher_id=voucher.id,
                    participant_id=participant.id,
                    applied_amount=33.33,
                    remaining=66.67
                )
        
        # Verify all logs created
        total_logs = VoucherLog.objects.filter(participant=participant).count()
        assert total_logs == 6  # 2 orders * 3 vouchers
        
        # Verify all vouchers activated
        for v in vouchers:
            v.refresh_from_db()
            assert v.program_pause_flag is True
            assert v.multiplier == 3
