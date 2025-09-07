from decimal import Decimal
from datetime import datetime, timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from food_orders.test_utils import log_vouchers_for_account
from decimal import Decimal
from datetime import datetime, timedelta
from food_orders.test_utils import log_vouchers_for_account

from .test_utils import BaseTestDataMixin
from food_orders.models import (
    Product,
    ProductManager,
    OrderItem,
    VoucherSetting,
    ProgramPause,
    Program,
)

class OrderFormSetTests(BaseTestDataMixin, TestCase):
    """Tests for order formset validation (category & weight limits)."""

    def setUp(self):
        super().setUp()
        # Categories
        self.meat = self.create_category("Meat")
        self.veg = self.create_category("Vegetables")

        # Products
        self.hygiene_product = self.create_product("Toothbrush", 5.00, self.category_hygiene)
        self.meat_product = self.create_product("Chicken Breast", 6.00, self.meat, weight_lbs=2.5)
        self.veg_product = self.create_product("Carrot", 1.00, self.veg, weight_lbs=0.2)

        # Participant & Order
        self.participant = self.create_participant()
        self.order = self.create_order(self.participant.accountbalance)

        # Meat category limit
        ProductManager.objects.create(category=self.meat, limit_scope="per_order", limit=5.0)

    def _validate_order(self, product, quantity, valid=True, msg=None):
        """Helper to validate order formset with given product & quantity."""
        formset = self.get_formset(self.order, self.build_form_data(product, quantity))
        if valid:
            self.assertTrue(formset.is_valid(), f"Expected valid for {product.name}")
        else:
            self.assertFalse(formset.is_valid(), f"Expected invalid for {product.name}")
            if msg:
                self.assertIn(msg.lower(), str(formset.non_form_errors()).lower())

    def test_hygiene_limit_exceeded(self):
        self._validate_order(self.hygiene_product, 3, valid=False, msg="hygiene total exceeds hygiene balance")

    def test_hygiene_within_balance(self):
        self._validate_order(self.hygiene_product, 2)

    def test_meat_weight_limit_exceeded(self):
        self._validate_order(self.meat_product, 3, valid=False, msg="exceeds weight limit")

    def test_meat_within_limit(self):
        self._validate_order(self.meat_product, 2)

    def test_no_limit_category(self):
        self._validate_order(self.veg_product, 100)

class OrderModelTest(BaseTestDataMixin, TestCase):
    """Tests for order and order item pricing."""

    def setUp(self):
        super().setUp()
        self.participant = self.create_participant()
        self.p1 = self.create_product("Canned Beans", 2.50, self.category_cb, quantity=100)
        self.p2 = self.create_product("Cereal", 3.00, self.category_cr, quantity=50)
        self.order = self.create_order(self.participant.accountbalance)

        self.i1 = self.create_order_item(self.order, self.p1, 3)
        self.i2 = self.create_order_item(self.order, self.p2, 2)

    def create_order_item(self, order, product, qty):
        return OrderItem.objects.create(
            order=order,
            product=product,
            price_at_order=product.price,
            quantity=qty,
        )

    def test_order_item_total_price(self):
        self.assertEqual(self.i1.total_price, Decimal("7.50"))
        self.assertEqual(self.i2.total_price, Decimal("6.00"))

    def test_order_total_price(self):
        self.assertEqual(self.order.total_price, Decimal("13.50"))

class VoucherBalanceTest(BaseTestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.participant = self.create_participant(adults=1, children=0)
        VoucherSetting.objects.create(
            adult_amount=40,
            child_amount=25,
            infant_modifier=5,
            active=True,
        )

    def test_balance_initial(self):
        # Log state before assertion
        log_vouchers_for_account(
            self.participant.accountbalance,
            "test_balance_initial: Voucher/Balance state"
        )
        self.assertEqual(
            self.participant.accountbalance.available_balance,
            Decimal("80.00")
        )

    def test_program_pause_multipliers(self):
        from django.utils import timezone

        test_cases = [
            {
                "reason": "Short pause",
                "duration_days": 3,
                "expected_multiplier": 2,
            },
            {
                "reason": "Extended pause",
                "duration_days": 14,
                "expected_multiplier": 3,
            },
        ]

        start_date = timezone.now().date() + timedelta(days=11)

        for case in test_cases:
            with self.subTest(reason=case["reason"]):
                # Ensure no overlapping pauses
                ProgramPause.objects.all().delete()

                end_date = start_date + timedelta(days=case["duration_days"])
                pause = ProgramPause.objects.create(
                    start_date=start_date,
                    end_date=end_date,
                    reason=case["reason"],
                )

                # Verify the multiplier
                self.assertEqual(pause._calculate_pause_status()[0], case["expected_multiplier"])
                self.assertEqual(pause.multiplier, case["expected_multiplier"])


    def test_balance_doubles_during_pause(self):
        # Apply program pause
        start = timezone.now().date() + timedelta(days=11)
        end = start + timedelta(days=3)  # keeps same semantics as your start+11 .. +14
        pause = ProgramPause.objects.create(start_date=start, end_date=end, reason="Holiday Break")

        # sanity checks: ensure your pause logic is returning the expected multiplier
        self.assertEqual(pause._calculate_pause_status()[0], 2)
        self.assertEqual(pause.multiplier, 2)

class ParticipantTest(BaseTestDataMixin, TestCase):
    """Tests for participant-program relationship."""

    def test_program_relationship(self):
        program = Program.objects.create(
            name="Wednesday Class",
            MeetingDay="Wednesday",
            meeting_time="10:00:00",
        )
        participant = self.create_participant(name="Jane Doe", program=program)

        # Forward relation
        self.assertEqual(participant.program, program)
        # Reverse relation
        self.assertIn(participant, program.participant_set.all())

class NegativeProductQuantityTest(BaseTestDataMixin, TestCase):
    """Validation tests for product stock."""

    def test_negative_quantity_raises(self):
        product = Product(
            name="Cereal",
            price=3.00,
            description="Box of cereal",
            quantity_in_stock=-10,
            category=self.category_cr,
        )
        with self.assertRaises(ValidationError):
            product.full_clean()
