from django.test import TestCase
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from datetime import datetime, timedelta

from .models import (
    Product, Participant, Order, OrderItem, AccountBalance,
    Voucher, VoucherSetting, Program, ProgramPause, ProductManager, Category
)
from .forms import OrderItemInlineFormSet


class BaseTestDataMixin:
    def create_category(self, name):
        return Category.objects.create(name=name)
    def setUp(self):
        self.category_cb = self.create_category("Canned Goods")
        self.category_cr = self.create_category("Cereal")
        self.category_hygiene = self.create_category("Hygiene")

    def create_product(self, name, price, category, weight_lbs=0.0, quantity=10):
        return Product.objects.create(
            name=name,
            price=price,
            category=category,
            weight_lbs=weight_lbs,
            quantity_in_stock=quantity
        )

    def create_participant(self, **kwargs):
        defaults = {"name": "Test User", "email": "test@example.com", "adults": 2, "children": 1}
        defaults.update(kwargs)
        return Participant.objects.create(**defaults)

    def create_order(self, account, status_type="pending"):
        return Order.objects.create(account=account, status_type=status_type)

    def get_formset(self, order, data):
        FormSet = inlineformset_factory(
            Order,
            OrderItem,
            formset=OrderItemInlineFormSet,
            fields=('product', 'quantity', 'price_at_order'),
            extra=1,
            can_delete=False
        )
        return FormSet(data=data, instance=order, prefix='orderitem_set')

    def build_form_data(self, product, quantity):
        return {
            'orderitem_set-TOTAL_FORMS': '1',
            'orderitem_set-INITIAL_FORMS': '0',
            'orderitem_set-MIN_NUM_FORMS': '0',
            'orderitem_set-MAX_NUM_FORMS': '1000',
            'orderitem_set-0-product': str(product.id),
            'orderitem_set-0-quantity': str(quantity),
            'orderitem_set-0-price_at_order': str(product.price),
        }


class OrderItemFormSetTest(BaseTestDataMixin, TestCase):
    def setUp(self):
        self.hygiene = self.create_category("Hygiene")
        self.meat = self.create_category("Meat")
        self.veg = self.create_category("Vegetables")
        self.hygiene_product = self.create_product("Toothbrush", 5.00, self.hygiene)
        self.meat_product = self.create_product("Chicken Breast", 6.00, self.meat, weight_lbs=2.5)
        self.veg_product = self.create_product("Carrot", 1.00, self.veg, weight_lbs=0.2)
        self.participant = self.create_participant()
        self.order = self.create_order(self.participant.accountbalance)

        ProductManager.objects.create(category=self.meat, limit_scope="per_order", limit=5.0)

    def test_hygiene_limit_exceeded(self):
        formset = self.get_formset(self.order, self.build_form_data(self.hygiene_product, 3))
        self.assertFalse(formset.is_valid())
        self.assertIn("Hygiene total exceeds hygiene balance", str(formset.non_form_errors()))

    def test_meat_weight_limit_exceeded(self):
        formset = self.get_formset(self.order, self.build_form_data(self.meat_product, 3))
        self.assertFalse(formset.is_valid())
        self.assertIn("exceeds weight limit", str(formset.non_form_errors()).lower())

    def test_meat_within_limit(self):
        formset = self.get_formset(self.order, self.build_form_data(self.meat_product, 2))
        self.assertTrue(formset.is_valid())

    def test_hygiene_within_balance(self):
        formset = self.get_formset(self.order, self.build_form_data(self.hygiene_product, 2))
        self.assertTrue(formset.is_valid())

    def test_no_limit_category(self):
        formset = self.get_formset(self.order, self.build_form_data(self.veg_product, 100))
        self.assertTrue(formset.is_valid())


class OrderModelTest(BaseTestDataMixin, TestCase):
    def setUp(self):
        super().setUp() 
        self.participant = self.create_participant()
        self.p1 = self.create_product("Canned Beans", 2.50, self.category_cb, quantity=100)
        self.p2 = self.create_product("Cereal", 3.00, self.category_cr, quantity=50)
        self.order = self.create_order(self.participant.accountbalance)
        self.i1 = OrderItem.objects.create(order=self.order, product=self.p1, price_at_order=self.p1.price, quantity=3)
        self.i2 = OrderItem.objects.create(order=self.order, product=self.p2, price_at_order=self.p2.price, quantity=2)

    def test_order_item_total_price(self):
        self.assertEqual(self.i1.total_price(), 7.50)
        self.assertEqual(self.i2.total_price(), 6.00)

    def test_order_total_price(self):
        self.assertEqual(self.order.total_price(), 13.50)


class VoucherAmountTest(BaseTestDataMixin, TestCase):
    def setUp(self):
        self.participant = self.create_participant(children=3, infant=True)
        self.vs = VoucherSetting.objects.create(adult_amount=40, child_amount=25, infant_modifier=5, active=True)
        self.account = self.participant.accountbalance
        self.v1 = Voucher.objects.create(account=self.account, voucher_type="Grocery", active=True)
        self.v2 = Voucher.objects.create(account=self.account, voucher_type="Grocery", active=True)
        self.v3 = Voucher.objects.create(account=self.account, voucher_type="Life")

    def test_grocery_voucher_with_infant(self):
        expected = 2 * 40 + 3 * 25 + 5
        total = sum(v.voucher_amnt() for v in Voucher.objects.filter(account=self.account))
        self.assertEqual(total, expected)

    def test_life_voucher_returns_zero_balance(self):
        self.assertEqual(self.v3.voucher_amnt(), 0)

    def test_use_both_vouchers(self):
        order = self.create_order(self.account, status_type="confirmed")
        order._test_price = 100
        order.used_voucher()
        self.v1.refresh_from_db()
        self.v2.refresh_from_db()
        self.assertFalse(self.v1.active)
        self.assertFalse(self.v2.active)

    def test_use_only_one_voucher(self):
        order = self.create_order(self.account, status_type="confirmed")
        order._test_price = 50
        order.used_voucher()
        self.v1.refresh_from_db()
        self.v2.refresh_from_db()
        self.assertFalse(self.v1.active)
        self.assertTrue(self.v2.active)


class AccountBalanceTest(BaseTestDataMixin, TestCase):
    def setUp(self):
        self.participant = self.create_participant(adults=1, children=0, infant=False)
        self.vs = VoucherSetting.objects.create(adult_amount=40, child_amount=25, infant_modifier=5, active=True)

    def test_balance_initial(self):
        balance = self.participant.accountbalance.voucher_balance
        self.assertEqual(balance, 80.00)

    def test_balance_doubles_during_pause(self):
        ProgramPause.objects.create(
            start_date=datetime.now() + timedelta(days=7),
            end_date=datetime.now() + timedelta(days=11),
            reason="Holiday Break"
        )
        self.assertEqual(self.participant.accountbalance.voucher_balance, 160.00)


class ParticipantTest(BaseTestDataMixin, TestCase):
    def test_program_relationship(self):
        program = Program.objects.create(name="Wednesday Class", MeetingDay="Wednesday", meeting_time="10:00:00")
        participant = self.create_participant(name="Jane Doe", program=program)
    
        # Forward relation
        self.assertEqual(participant.program, program)
    
        # Reverse relation: should include participant in the set
        self.assertIn(participant, program.participant_set.all())



class NegativeProductQuantityTest(BaseTestDataMixin, TestCase):
    def test_negative_quantity_raises(self):
        with self.assertRaises(ValidationError):
            product = Product(name="Cereal", price=3.00, description="Box of cereal", quantity_in_stock=-10, category=self.category_cr)
            product.full_clean()
