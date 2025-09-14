from freezegun import freeze_time
from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from unittest import mock
import logging

from food_orders.models import (
    Participant,
    Voucher,
    ProgramPause,
    VoucherSetting,
    AccountBalance,
    voucher_utils
)
from food_orders.tasks import update_voucher_flag

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ProgramPauseSignalTests(TestCase):

    def setUp(self):
        """Set up a participant, account, vouchers, and voucher settings."""
        self.participant = Participant.objects.create(
            name="Test Participant",
            email="test@testway.com",
            active=True
        )
        self.account = AccountBalance.objects.get_or_create(participant=self.participant)[0]

        self.vs = VoucherSetting.objects.create(
            adult_amount=40,
            child_amount=25,
            infant_modifier=5,
            active=True
        )

        # Patch voucher calculation to always return 40
        patcher = mock.patch(
            'food_orders.models.voucher_utils.calculate_voucher_amount',
            return_value=Decimal(40)
        )
        self.addCleanup(patcher.stop)
        self.mock_calculate_amount = patcher.start()

        # Create vouchers
        self.v1 = Voucher.objects.create(account=self.account, voucher_type="grocery", active=True)
        self.v2 = Voucher.objects.create(account=self.account, voucher_type="grocery", active=True)
        self.v3 = Voucher.objects.create(account=self.account, voucher_type="grocery", active=False)

        self.pause_duration = timedelta(days=14)

    # ----------------------------
    # Helpers
    # ----------------------------
    def _refresh_all(self):
        """Refresh account + all vouchers."""
        self.account.refresh_from_db()
        self.v1.refresh_from_db()
        self.v2.refresh_from_db()
        self.v3.refresh_from_db()

    def _count_flagged_active(self, vouchers):
        return sum(1 for v in vouchers if v.active and v.program_pause_flag)

    def _trigger_program_pause(self, start=None, end=None):
        """Create a ProgramPause and trigger voucher update task synchronously."""
        start = start or timezone.now()
        end = end or start + self.pause_duration
        pp = ProgramPause.objects.create(pause_start=start, pause_end=end, reason="Test Pause")
        # Synchronously update vouchers
        update_voucher_flag(pp.id)
        return pp

    # ----------------------------
    # Tests
    # ----------------------------
    @freeze_time("2025-09-13 19:16:38")
    def test_signal_flags_two_active_vouchers(self):
        start = timezone.now()
        end = start + self.pause_duration

        self._trigger_program_pause(start, end)

        self._refresh_all()
        flagged_active = self._count_flagged_active([self.v1, self.v2, self.v3])
        self.assertEqual(flagged_active, 2)
        self.assertFalse(self.v3.program_pause_flag)

    @freeze_time("2025-09-13 19:16:38")
    def test_signal_idempotency(self):
        start = timezone.now()
        end = start + self.pause_duration

        pp = self._trigger_program_pause(start, end)
        pp.save()
        pp.save()  # saving multiple times should not break flags

        self._refresh_all()
        self.assertTrue(self.v1.program_pause_flag)
        self.assertTrue(self.v2.program_pause_flag)
        self.assertFalse(self.v3.program_pause_flag)

    @freeze_time("2025-09-13 19:16:38")
    def test_participant_with_single_voucher(self):
        participant2 = Participant.objects.create(name="P2", email="p2@test.com", active=True)
        account_balance = AccountBalance.objects.get_or_create(participant=participant2)[0]
        v = Voucher.objects.create(account=account_balance, active=True)

        start = timezone.now()
        end = start + self.pause_duration
        self._trigger_program_pause(start, end)

        v.refresh_from_db()
        self.assertTrue(v.program_pause_flag)

    @freeze_time("2025-09-13 19:16:38")
    def test_voucher_balance_doubles_during_pause(self):
        # Add extra voucher if participant has adults
        for _ in range(max(1, getattr(self.participant, "adults", 1))):
            Voucher.objects.create(account=self.account, voucher_type="grocery", active=True)

        self.account.refresh_from_db()
        initial_balance = self.account.available_balance
        self.assertGreater(initial_balance, 0)

        start = timezone.now()
        end = start + self.pause_duration
        self._trigger_program_pause(start, end)

        # refresh all vouchers
        for v in self.account.vouchers.all():
            v.refresh_from_db()
        self.account.refresh_from_db()
        balance_during_pause = self.account.available_balance

        self.assertEqual(balance_during_pause, initial_balance * 2)

    @freeze_time("2025-09-13 19:16:38")
    def test_signal_flags_two_active_vouchers_verbose(self):
        start = timezone.now()
        end = start + self.pause_duration
        logger.info("=== Starting verbose voucher flag test ===")

        self._trigger_program_pause(start, end)

        self._refresh_all()
        self.assertTrue(self.v1.program_pause_flag)
        self.assertTrue(self.v2.program_pause_flag)
        self.assertFalse(self.v3.program_pause_flag)

        flagged_count = self._count_flagged_active([self.v1, self.v2, self.v3])
        self.assertEqual(flagged_count, 2)

        expected_balance = sum(
            v.voucher_amnt * v.multiplier
            for v in Voucher.objects.filter(account=self.account, active=True)
        )
        self.account.refresh_from_db()
        self.assertEqual(self.account.available_balance, expected_balance)

        logger.info("=== Verbose voucher flag test complete ===")
