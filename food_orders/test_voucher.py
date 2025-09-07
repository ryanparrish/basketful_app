from datetime import datetime, timedelta
from decimal import Decimal

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


class VoucherAmountTest(BaseTestDataMixin, TestCase):

    def setUp(self):
        # Create voucher settings first
        self.vs = VoucherSetting.objects.create(
            adult_amount=40,
            child_amount=25,
            infant_modifier=5,
            active=True,
        )
        super().setUp()

        # Create participant and account (triggers signals to create vouchers)
        self.participant = self.create_participant(children=3, email="test@test.com")
        self.account = self.participant.accountbalance
        log_vouchers_for_account(self.account, "After participant creation")

        # Store expected total for reuse
        self.expected = (2 * 40) + (25 * 3)  # adults + children

    def test_grocery_voucher_with_infant(self):
        self.participant.diaper_count += 1
        self.participant.save(update_fields=["diaper_count"])
        self.expected += self.vs.infant_modifier

        log_vouchers_for_account(
            self.account,
            f"test_grocery_voucher_with_infant: After adding infant (Participant {self.participant.id})"
        )

        grocery_sum = sum(
            v.voucher_amnt
            for v in Voucher.objects.filter(account=self.account, voucher_type__iexact="grocery")
        )
        test_logger.info(
            f"Expected total: {self.expected}, "
            f"Available balance: {self.account.available_balance}, "
            f"Sum of grocery vouchers: {grocery_sum}"
        )

        first_grocery = Voucher.objects.filter(
            account=self.account, voucher_type__iexact="grocery"
        ).first()
        self.assertIsNotNone(first_grocery, "No grocery voucher was assigned")
        self.assertEqual(first_grocery.voucher_amnt, self.expected)

    def test_life_voucher_returns_zero_balance(self):
        Voucher.objects.create(account=self.account, active=True, voucher_type="life")
        life_voucher = Voucher.objects.filter(
            account=self.account, voucher_type__iexact="life"
        ).first()
        self.assertIsNotNone(life_voucher, "No life voucher was assigned")
        self.assertEqual(life_voucher.voucher_amnt, 0)

    def test_use_both_vouchers(self):
        # Create order in pending state
        order = self.create_order(self.account, status_type="pending")
        order._test_price = 350

        # Confirm the order (triggers voucher application)
        order.status_type = "confirmed"
        order.save()

        grocery_vouchers = list(
            Voucher.objects.filter(account=self.account, voucher_type__iexact="grocery")
        )
        self.assertGreaterEqual(len(grocery_vouchers), 2, "Need at least 2 grocery vouchers")

        # Refresh DB state
        for v in grocery_vouchers:
            v.refresh_from_db()

        log_vouchers_for_account(
            self.account,
            context="test_use_both_vouchers: After order confirmation",
            order=order,
     )

        # Assert first two vouchers were used
        self.assertFalse(grocery_vouchers[0].active, "First grocery voucher should be inactive")
        self.assertFalse(grocery_vouchers[1].active, "Second grocery voucher should be inactive")
        self.assertTrue(order.paid)
    
    def test_use_only_one_voucher(self):
        order = self.create_order(self.account, status_type="confirmed")
        order._test_price = 50
        order.save()

        grocery_vouchers = list(
            Voucher.objects.filter(account=self.account, voucher_type__iexact="grocery")
        )
        self.assertGreaterEqual(len(grocery_vouchers), 2, "Need at least 2 grocery vouchers")

        for v in grocery_vouchers:
            v.refresh_from_db()

        inactive = [v for v in grocery_vouchers if not v.active]
        active = [v for v in grocery_vouchers if v.active]

        self.assertEqual(len(inactive), 1, "Expected exactly one voucher to be used")
        self.assertGreaterEqual(len(active), 1, "Expected at least one voucher to remain active")

    def test_voucher_marked_as_used_after_order(self):
        order = self.create_order(self.account, status_type="confirmed")
        order._test_price = 50
        order.save()

        grocery_voucher = Voucher.objects.filter(
            account=self.account, voucher_type__iexact="grocery"
        ).first()
        grocery_voucher.refresh_from_db()
        self.assertFalse(grocery_voucher.active, "Voucher should be marked as used")

    def test_voucher_cannot_be_reused(self):
        order1 = self.create_order(self.account, status_type="confirmed")
        order1._test_price = 50
        order1.save()

        grocery_voucher = Voucher.objects.filter(
            account=self.account, voucher_type__iexact="grocery"
        ).first()
        grocery_voucher.refresh_from_db()
        self.assertFalse(grocery_voucher.active)

        order2 = self.create_order(self.account, status_type="confirmed")
        order2._test_price = 50
        order2.save()

        grocery_voucher.refresh_from_db()
        self.assertFalse(grocery_voucher.active, "Voucher cannot be reused after being used once")


class VoucherPauseTest(BaseTestDataMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.participant = self.create_participant(adults=1, children=1, diaper_count=1)
        VoucherSetting.objects.create(adult_amount=40, child_amount=25, infant_modifier=5, active=True)
        self.account_balance = self.participant.accountbalance

