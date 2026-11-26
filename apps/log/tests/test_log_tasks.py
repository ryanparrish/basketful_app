"""
Comprehensive tests for log task functions.

Tests cover:
- log_voucher_application_task: Voucher application logging
- Edge cases
"""

import pytest
from decimal import Decimal

from apps.log.tasks.logs import log_voucher_application_task
from apps.log.models import VoucherLog
from apps.voucher.models import Voucher, VoucherSetting
from apps.account.models import Participant, AccountBalance
from apps.lifeskills.models import Program


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
