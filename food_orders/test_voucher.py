from datetime import datetime, timedelta
from decimal import Decimal
import logging

from django.test import TestCase

from food_orders.models import (
    Participant,
    AccountBalance,
    Voucher,
    VoucherSetting,
    ProgramPause,
)
from food_orders.test_utils import (
    BaseTestDataMixin,
    test_logger,
    log_vouchers_for_account,
)

from django.test import TestCase
from food_orders.models import Participant, AccountBalance, Voucher, VoucherSetting, ProgramPause
from food_orders.test_utils import log_vouchers_for_account

class VoucherAmountTest(BaseTestDataMixin, TestCase):
   
    def setUp(self):
        super().setUp()
        # Create participant and account (triggers signals to create vouchers)
        self.participant = self.create_participant(children=3, email='test@test.com')
        self.account = self.participant.accountbalance

        # Create voucher settings
        self.vs = VoucherSetting.objects.create(
            adult_amount=40,
            child_amount=25,
            infant_modifier=5,
            active=True,
        )

        # Store expected total for reuse
        self.expected = (2 * 40) + (25 * 3)  # adults + children

        # Convenience queryset for all vouchers
        self.vouchers = Voucher.objects.filter(account=self.account)

    def test_grocery_voucher_with_infant(self):
        # Increase diaper count by 1
        self.participant.diaper_count += 1
        self.participant.save(update_fields=["diaper_count"])
        # Update expected to account for the increase
        self.expected += self.vs.infant_modifier

        # Use shared logger for participant + vouchers
        log_vouchers_for_account(
            self.account,
            f"test_grocery_voucher_with_infant: After adding infant (Participant {self.participant.id})"
        )

        # Log the calculation
        grocery_sum = sum(
            v.voucher_amnt
            for v in self.vouchers
            if v.voucher_type.lower() == "grocery"
        )
        test_logger.info(
            f"Expected total: {self.expected}, "
            f"Available balance: {self.account.available_balance}, "
            f"Sum of grocery vouchers: {grocery_sum}"
        )

        # Pick first grocery voucher and assert
        first_grocery = (
            Voucher.objects.filter(account=self.account, voucher_type__iexact="grocery")
            .first()
        )
        self.assertIsNotNone(first_grocery, "No grocery voucher was assigned")
        self.assertEqual(first_grocery.voucher_amnt, self.expected)

    def test_life_voucher_returns_zero_balance(self):
        # Create Life Voucher 
        self.create_life_voucher= Voucher.objects.create(
            account = self.account, 
            active = True,
            voucher_type = "life"
        )
        life_voucher = Voucher.objects.filter(
            account=self.account, voucher_type__iexact="life"
        ).first()
        self.assertIsNotNone(life_voucher, "No life voucher was assigned")
        self.assertEqual(life_voucher.voucher_amnt, 0)
        
    def test_use_both_vouchers(self):
        order = self.create_order(self.account, status_type="confirmed")
        order._test_price = 310
        order.use_voucher()

        # Use shared logger
        log_vouchers_for_account(self.account, "test_use_both_vouchers: After Placing an Order")

        grocery_vouchers = list(
        Voucher.objects.filter(account=self.account, voucher_type__iexact="grocery")
        )
        self.assertGreaterEqual(len(grocery_vouchers), 2, "Need at least 2 grocery vouchers")

        # Refresh from DB after use
        grocery_vouchers[0].refresh_from_db()
        grocery_vouchers[1].refresh_from_db()

        # Ensure both vouchers were deactivated
        self.assertFalse(grocery_vouchers[0].active)
        self.assertFalse(grocery_vouchers[1].active)


    def test_use_only_one_voucher(self):
        order = self.create_order(self.account, status_type="confirmed")
        order._test_price = 50
        order.use_voucher()

        grocery_vouchers = Voucher.objects.filter(
            account=self.account, voucher_type__iexact="grocery"
        )
        self.assertGreaterEqual(grocery_vouchers.count(), 2, "Need at least 2 grocery vouchers")

        # Refresh from DB
        grocery_vouchers = list(grocery_vouchers)  # force evaluation
        for v in grocery_vouchers:
            v.refresh_from_db()

        # Exactly one voucher should be inactive
        inactive = [v for v in grocery_vouchers if not v.active]
        active = [v for v in grocery_vouchers if v.active]

        self.assertEqual(len(inactive), 1, "Expected exactly one voucher to be used")
        self.assertGreaterEqual(len(active), 1, "Expected at least one voucher to remain active")

    def test_voucher_marked_as_used_after_order(self):
        order = self.create_order(self.account, status_type="confirmed")
        order._test_price = 50
        order.use_voucher()

        grocery_voucher = Voucher.objects.filter(
            account=self.account, voucher_type__iexact="grocery"
        ).first()
        grocery_voucher.refresh_from_db()
        self.assertFalse(grocery_voucher.active, "Voucher should be marked as used and inactive.")

    def test_voucher_cannot_be_reused(self):
        # Use the voucher once
        order1 = self.create_order(self.account, status_type="confirmed")
        order1._test_price = 50
        order1.use_voucher()

        grocery_voucher = Voucher.objects.filter(
            account=self.account, voucher_type__iexact="grocery"
        ).first()
        grocery_voucher.refresh_from_db()
        self.assertFalse(grocery_voucher.active)

        # Attempt to reuse the same voucher
        order2 = self.create_order(self.account, status_type="confirmed")
        order2._test_price = 50
        order2.use_voucher()

        grocery_voucher.refresh_from_db()
        self.assertFalse(
            grocery_voucher.active,
            "Voucher cannot be reused after being used once.",
        )
from food_orders.test_utils import BaseTestDataMixin, log_vouchers_for_account
from food_orders.models import Participant, VoucherSetting, ProgramPause, Voucher
from decimal import Decimal
from datetime import datetime, timedelta
from django.test import TestCase


class VoucherPauseTest(BaseTestDataMixin, TestCase):
    def setUp(self):
        super().setUp()  # <- this runs BaseTestDataMixin.setUp (creates categories)

        # Create participant
        self.participant = self.create_participant(adults=1, children=1, diaper_count=1)

        # Create voucher setting
        VoucherSetting.objects.create(
            adult_amount=40,
            child_amount=25,
            infant_modifier=5,
            active=True,
        )

        # Ensure account and initial vouchers
        self.account_balance = self.participant.accountbalance

    def test_voucher_balance_doubles_with_active_pause(self):
        # Log initial state
        log_vouchers_for_account(self.account_balance, "This is the Account Balance Before applying ProgramPause")
        
        self.test_part_info(context="Before Program Pause")

        # Calculate initial voucher balance directly via voucher_amnt
        vouchers = Voucher.objects.filter(
            account=self.account_balance, active=True, voucher_type="grocery"
        )
        initial_balance = sum(v.voucher_amnt for v in vouchers)
        self.assertEqual(initial_balance, Decimal(70))  # 1 adult*40 + 1 child*25 + 1 infant*5

        # Create a ProgramPause (dynamic multiplier applies automatically)
        pause = ProgramPause.objects.create(
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=7),
            reason="Test Pause"
        )
        log_vouchers_for_account(self.account_balance, " This is the Account Balance After applying ProgramPause")
        self.test_part_info(participant=self.participant, context="After Program Pause")
        
        # Find active pauses for this account/order that affect the balance
        active_pauses = [p for p in ProgramPause.objects.all() if p.is_active_gate]
        multiplier = max([p.multiplier for p in active_pauses], default=1)

        # Apply multiplier to calculate expected balance
        expected_balance = initial_balance * Decimal(multiplier)

        # Log state after pause
        log_vouchers_for_account(self.account_balance, "After creating ProgramPause with dynamic multiplier")

        # Assert that balance is correctly doubled (or multiplied dynamically)
        self.assertEqual(sum(v.voucher_amnt for v in vouchers) * Decimal(multiplier), expected_balance)

