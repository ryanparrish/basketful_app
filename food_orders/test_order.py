from django.test import TestCase
from food_orders.models import Product, Category, Order, AccountBalance, Participant
from food_orders.order_utils import OrderUtils

class ValidateOrderItemsTest(TestCase):
    def setUp(self):
        # Create a participant
        self.participant = Participant.objects.create(
            adults=1,
            children=0,
            diaper_count=0,
        )

        # Create account balance linked to participant
        self.account_balance = AccountBalance.objects.create(
            participant=self.participant,
            _hygiene_balance=100,  # Use the actual underlying field names
            _voucher_balance=100
        )

        # Create a category
        self.category = Category.objects.create(name="Test Category")

        # Create multiple products in the same category
        self.product1 = Product.objects.create(
            name="Product 1",
            category=self.category,
            price=5,
            quantity_in_stock=10
        )
        self.product2 = Product.objects.create(
            name="Product 2",
            category=self.category,
            price=10,
            quantity_in_stock=10
        )

        # Dummy order item data
        self.items = [
            type("OrderItemData", (), {"product": self.product1, "quantity": 1}),
            type("OrderItemData", (), {"product": self.product2, "quantity": 2}),
        ]

    # Helper to create an order
    def create_order(self):
        return Order.objects.create(account=self.account_balance)

    # Helper to add items to an order
    def add_items_to_order(self, order, items):
        for item in items:
            order.items.create(product=item.product, quantity=item.quantity)

    # Test for the multiple objects edge case
    def test_multiple_objects_error(self):
        with self.assertRaises(Product.MultipleObjectsReturned):
            Product.objects.get(category_id=self.category.id)

    # Test creating an order and adding items
    def test_create_order_and_add_items(self):
        order = self.create_order()
        self.add_items_to_order(order, self.items)
        self.assertEqual(order.items.count(), len(self.items))

    # Test the validate_order_items function
    def test_validate_order_items_refactored(self):
        utils = OrderUtils()
        try:
            utils.validate_order_items(
                items=self.items,
                participant=self.participant,
                account_balance=self.account_balance,
                user=None,
            )
        except Exception as e:
            self.fail(f"validate_order_items raised an exception unexpectedly: {e}")

    # Test hygiene balance enforcement
    def test_hygiene_balance_limit(self):
        # Make a hygiene product
        hygiene_category = Category.objects.create(name="Hygiene")
        hygiene_product = Product.objects.create(
            name="Soap",
            category=hygiene_category,
            price=150,  # Exceeds balance
            quantity_in_stock=10
        )
        items = [type("OrderItemData", (), {"product": hygiene_product, "quantity": 1})]
        utils = OrderUtils()
        with self.assertRaises(Exception) as cm:
            utils.validate_order_items(
                items=items,
                participant=self.participant,
                account_balance=self.account_balance,
            )
        self.assertIn("exceeds hygiene balance", str(cm.exception))

    # Test voucher balance enforcement
    def test_voucher_balance_limit(self):
        expensive_product = Product.objects.create(
            name="Expensive Item",
            category=self.category,
            price=200,  # Exceeds voucher balance
            quantity_in_stock=10
        )
        items = [type("OrderItemData", (), {"product": expensive_product, "quantity": 1})]
        utils = OrderUtils()
        with self.assertRaises(Exception) as cm:
            utils.validate_order_items(
                items=items,
                participant=self.participant,
                account_balance=self.account_balance,
            )
        self.assertIn("exceeds available voucher balance", str(cm.exception))
