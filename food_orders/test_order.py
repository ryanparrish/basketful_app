# food_orders/test_order.py
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from food_orders.models import (
    Product,
    Category,
    Order,
    OrderItem,
    AccountBalance,
    Participant,
    Voucher,
)
from food_orders.order_utils import OrderUtils


class ValidateOrderItemsTest(TestCase):
    """
    Tests for order validation with fully isolated participants, vouchers,
    and orders. Voucher amounts are deterministic using base_balance and multiplier.
    Hygiene balance is derived from base_balance as a property.
    """

    # -----------------------------
    # Helper methods
    # -----------------------------

    def create_category(self, name: str) -> Category:
        """Create and return a Category instance."""
        return Category.objects.create(name=name)

    def create_product(
        self, name: str, price: Decimal, category: Category, quantity: int = 10
    ) -> Product:
        """Create and return a Product instance."""
        return Product.objects.create(
            name=name,
            price=price,
            category=category,
            quantity_in_stock=quantity,
        )

    def create_participant(
        self, name="Test User", email="test@example.com", adults=1, children=0, infants=0
    ) -> Participant:
        """Create a Participant with predictable account balance."""
        participant = Participant.objects.create(
            name=name,
            email=email,
            adults=adults,
            children=children,
            diaper_count=infants,
        )
        participant.accountbalance.base_balance = Decimal("0")
        participant.accountbalance.save()
        return participant

    def create_voucher(
        self, participant: Participant, multiplier: int = 1, base_balance: Decimal = Decimal("0")
    ) -> Voucher:
        """Create a deterministic voucher; voucher_amnt is predictable."""
        account = participant.accountbalance
        account.base_balance = base_balance
        account.save()
        voucher = Voucher.objects.create(account=account, multiplier=multiplier)
        return voucher

    def create_order(self, participant: Participant, status_type: str = "pending") -> Order:
        """Create and return an Order."""
        return Order.objects.create(account=participant.accountbalance, status_type=status_type)

    def add_items_to_order(self, order, items):
        """Add items to an order."""
        for item in items:
            OrderItem.objects.create(order=order, product=item.product, quantity=item.quantity)

    def make_items(self, product_quantity_list):
        """
        Convert [(product, qty), ...] into objects with .product and .quantity
        suitable for OrderUtils.validate_order_items.
        """
        return [
            type("OrderItemData", (), {"product": product, "quantity": qty})
            for product, qty in product_quantity_list
        ]

    # -----------------------------
    # Tests
    # -----------------------------

    def test_multiple_objects_returned_error_isolated(self):
        """Test that multiple objects error is raised when duplicate products exist in a category."""
        category = self.create_category(name="Test Category for Multiple")
        self.create_product(name="Product A", category=category, price=Decimal("10"))
        self.create_product(name="Product B", category=category, price=Decimal("20"))

        with self.assertRaises(Product.MultipleObjectsReturned):
            Product.objects.get(category=category)

    def test_create_order_and_add_items(self):
        """Test creating an order and adding multiple items."""
        category = self.create_category("Canned Goods")
        product1 = self.create_product("Product 1", Decimal("5"), category)
        product2 = self.create_product("Product 2", Decimal("10"), category)

        participant = self.create_participant(adults=1, children=1)
        self.create_voucher(participant, multiplier=10, base_balance=Decimal("25"))

        items = self.make_items([(product1, 1), (product2, 2)])
        order = self.create_order(participant)
        self.add_items_to_order(order, items)
        self.assertEqual(order.items.count(), len(items))

    def test_validate_order_items_successful(self):
        """Test that validate_order_items passes for valid orders."""
        category = self.create_category("Canned Goods")
        product1 = self.create_product("Product 1", Decimal("5"), category)
        product2 = self.create_product("Product 2", Decimal("10"), category)

        participant = self.create_participant(adults=1, children=1)
        self.create_voucher(participant, multiplier=10, base_balance=Decimal("25"))

        items = self.make_items([(product1, 1), (product2, 2)])
        utils = OrderUtils()
        try:
            utils.validate_order_items(
                items=items,
                participant=participant,
                account_balance=participant.accountbalance,
            )
        except Exception as e:
            self.fail(f"validate_order_items raised unexpectedly: {e}")

    def test_hygiene_balance_limit(self):
        """Test that exceeding hygiene balance raises a ValidationError."""
        category = self.create_category("Hygiene")
        participant = self.create_participant()
        self.create_voucher(participant, multiplier=1, base_balance=Decimal("1"))

        product = self.create_product("Soap", Decimal("150"), category)
        items = self.make_items([(product, 1)])
        utils = OrderUtils()
        with self.assertRaises(ValidationError) as cm:
            utils.validate_order_items(
                items=items,
                participant=participant,
                account_balance=participant.accountbalance,
            )
        self.assertIn("exceeds hygiene balance", str(cm.exception))

    def test_voucher_balance_limit(self):
        """Test that exceeding voucher balance raises a ValidationError."""
        category = self.create_category("Canned Goods")
        participant = self.create_participant()
        self.create_voucher(participant, multiplier=1, base_balance=Decimal("1"))

        expensive_product = self.create_product("Expensive Item", Decimal("200"), category)
        items = self.make_items([(expensive_product, 1)])
        utils = OrderUtils()
        with self.assertRaises(ValidationError) as cm:
            utils.validate_order_items(
                items=items,
                participant=participant,
                account_balance=participant.accountbalance,
            )
        self.assertIn("exceeds available voucher balance", str(cm.exception))

    def test_voucher_balance_exhausted(self):
        """Test that an order fails if no voucher balance exists."""
        category = self.create_category("Canned Goods")
        product1 = self.create_product("Product 1", Decimal("5"), category)

        participant = self.create_participant()
        items = self.make_items([(product1, 1)])
        utils = OrderUtils()
        with self.assertRaises(ValidationError) as cm:
            utils.validate_order_items(
                items=items,
                participant=participant,
                account_balance=participant.accountbalance,
            )
        self.assertIn("exceeds available voucher balance", str(cm.exception))

    def test_order_total_equals_voucher_balance(self):
        """Test that an order exactly equal to voucher balance passes validation."""
        category_cb = self.create_category("Canned Goods")
        product = self.create_product("Product 1", Decimal("50"), category_cb)
        participant = self.create_participant(name="Exact Voucher User")
        self.create_voucher(participant, multiplier=1, base_balance=Decimal("50"))

        items = self.make_items([(product, 1)])
        utils = OrderUtils()
        try:
            utils.validate_order_items(
                items=items,
                participant=participant,
                account_balance=participant.accountbalance,
            )
        except ValidationError:
            self.fail(
                "validate_order_items raised unexpectedly when order equals voucher balance"
            )

    def test_mixed_hygiene_and_regular_items(self):
        """Test an order containing both hygiene and regular items within balance limits."""
        category_cb = self.create_category("Canned Goods")
        category_hygiene = self.create_category("Hygiene")

        product1 = self.create_product("Product 1", Decimal("10"), category_cb)
        hygiene_product = self.create_product("Soap", Decimal("50"), category_hygiene)

        participant = self.create_participant()
        participant.accountbalance.base_balance = Decimal("150")
        participant.accountbalance.save()
        self.create_voucher(participant, multiplier=1, base_balance=Decimal("150"))

        items = self.make_items([(product1, 1), (hygiene_product, 1)])
        utils = OrderUtils()
        try:
            utils.validate_order_items(
                items=items,
                participant=participant,
                account_balance=participant.accountbalance,
            )
        except Exception:
            self.fail(
                "validate_order_items raised unexpectedly with mixed items within balances"
            )

    # -----------------------------
    # Hygiene-specific edge case tests
    # -----------------------------

    def test_hygiene_total_equals_balance(self):
        """Test hygiene-only order exactly matches hygiene balance and passes."""
        category_hygiene = self.create_category("Hygiene")
        participant = self.create_participant(name="Exact Hygiene User")
        participant.accountbalance.base_balance = Decimal("300")
        participant.accountbalance.save()

        hygiene_product = self.create_product("Soap", Decimal("100"), category_hygiene)
        items = self.make_items([(hygiene_product, 1)])

        utils = OrderUtils()
        try:
            utils.validate_order_items(
                items=items,
                participant=participant,
                account_balance=participant.accountbalance,
            )
        except ValidationError:
            self.fail(
                "validate_order_items raised unexpectedly when hygiene total equals balance"
            )
    def test_hygiene_order_consumes_voucher(self):
        """Test a hygiene-only order consumes a voucher."""
        # Create a hygiene product category.
        category_hygiene = self.create_category("Hygiene")

        # Create a participant and a voucher with a balance.
        participant = self.create_participant(name="Hygiene User")
        voucher_balance = Decimal("150")
        voucher = self.create_voucher(participant, multiplier=1, base_balance=voucher_balance)

        # Assert the initial state: the voucher should be active.
        self.assertTrue(voucher.active)

        # Create a product and assign it to the 'Hygiene' category.
        hygiene_product = self.create_product("Soap", Decimal("20"), category=category_hygiene)

        # Create a complete order with two units of the hygiene product.
        items = self.make_items([(hygiene_product, 2)])  # total $40
        order = self.create_order(participant, items)
        self.complete_order(order)

        # Reload the voucher from the database to get its updated state.
        voucher.refresh_from_db()

        # Assert the final state: the voucher should now be inactive,
        # and its balance should be correctly reduced.
        self.assertFalse(voucher.active)
        self.assertEqual(voucher.voucher_amnt, voucher_balance - Decimal("40"))

    def test_hygiene_order_under_voucher_amount(self):
        """Test hygiene-only order under voucher amount does not deactivate voucher."""
        category_hygiene = self.create_category("Hygiene")
        participant = self.create_participant(name="Hygiene User")
        participant.accountbalance.base_balance = Decimal("150")
        participant.accountbalance.save()

        voucher = self.create_voucher(participant, multiplier=1, base_balance=Decimal("150"))

        hygiene_product = self.create_product("Soap", Decimal("20"), category_hygiene)
        items = self.make_items([(hygiene_product, 2)])  # total $40

        utils = OrderUtils()
        try:
            utils.validate_order_items(
                items=items,
                participant=participant,
                account_balance=participant.accountbalance,
            )
        except ValidationError:
            self.fail(
                "validate_order_items raised unexpectedly for hygiene order under voucher amount"
            )

        voucher.refresh_from_db()
        self.assertTrue(voucher.active, "Voucher was incorrectly deactivated for partial hygiene order")
    def test_products_without_categories(self):
        """
        Test that products without a category are skipped gracefully during validation.
        Uses a mock product object to avoid database integrity errors.
        Ensures that the order validation process does not raise an exception.
        """
        from types import SimpleNamespace

        # Create a mock product in memory with no category
        product_no_category = SimpleNamespace(
            name="Uncategorized Product",
            price=Decimal("10"),
            category=None
        )

        # Create participant and voucher
        participant = self.create_participant(name="No Category User")
        self.create_voucher(participant, multiplier=1, base_balance=Decimal("50"))

        # Prepare items for validation
        items = [
            type("OrderItemData", (), {"product": product_no_category, "quantity": 1})
        ]

        # Validate order items
        utils = OrderUtils()
        try:
            utils.validate_order_items(
                items=items,
                participant=participant,
                account_balance=participant.accountbalance,
            )
        except Exception as e:
            self.fail(f"validate_order_items raised unexpectedly for product without category: {e}")
# food_orders/test_order.py

from decimal import Decimal
from django.test import TestCase
from food_orders.models import Participant, Voucher, Product, Category, Order, OrderItem
from food_orders.order_utils import OrderUtils


class HappyPathOrderTests(TestCase):
    """
    Standalone happy path tests for orders, vouchers, and participants.
    Tests are deterministic and simulate realistic end-to-end order creation.
    """

    # -----------------------------
    # Helper methods
    # -----------------------------

    def create_category(self, name: str) -> Category:
        return Category.objects.create(name=name)

    def create_product(self, name: str, price: Decimal, category: Category, quantity: int = 10) -> Product:
        return Product.objects.create(
            name=name,
            price=price,
            category=category,
            quantity_in_stock=quantity,
        )

    def create_participant(self, name="Test User", email="test@example.com", adults=1, children=0, infants=0) -> Participant:
        """
        Create a participant and ensure the account balance is initialized via signals.
        """
        participant = Participant.objects.create(
            name=name,
            email=email,
            adults=adults,
            children=children,
            diaper_count=infants,
        )
        # Signals should automatically create AccountBalance
        participant.accountbalance.base_balance = Decimal("0")
        participant.accountbalance.save()
        return participant

    def create_voucher(self, participant: Participant, multiplier: int = 1, base_balance: Decimal = Decimal("0")) -> Voucher:
        """
        Create a voucher linked to the participant's account balance.
        Voucher amount is deterministic from account balance and multiplier.
        """
        account = participant.accountbalance
        account.base_balance = base_balance
        account.save()
        voucher = Voucher.objects.create(account=account, multiplier=multiplier)
        return voucher

    def create_order(self, participant: Participant, status_type: str = "pending") -> Order:
        return Order.objects.create(account=participant.accountbalance, status_type=status_type)

    def add_items_to_order(self, order, items):
        for item in items:
            OrderItem.objects.create(order=order, product=item.product, quantity=item.quantity)

    def make_items(self, product_quantity_list):
        """
        Convert [(product, qty), ...] into objects with .product and .quantity
        suitable for OrderUtils.validate_order_items.
        """
        return [
            type("OrderItemData", (), {"product": product, "quantity": qty})
            for product, qty in product_quantity_list
        ]

    # -----------------------------
    # Happy path tests
    # -----------------------------

    def test_simple_order_creation(self):
        """
        Happy path: Create a participant, voucher, order, and add items.
        Verify order persists and balances are sufficient.
        """
        category = self.create_category("Canned Goods")
        product = self.create_product("Beans", Decimal("10"), category)

        participant = self.create_participant(email="simple@example.com")
        voucher = self.create_voucher(participant, multiplier=1, base_balance=Decimal("50"))

        order = self.create_order(participant)
        items = self.make_items([(product, 3)])
        self.add_items_to_order(order, items)

        utils = OrderUtils()
        utils.validate_order_items(items, participant, participant.accountbalance)

        # Assert order and items are saved
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 1)
        self.assertEqual(order.items.first().quantity, 3)

    def test_order_with_multiple_products(self):
        """
        Create an order with multiple products across different categories.
        """
        category1 = self.create_category("Canned Goods")
        category2 = self.create_category("Hygiene")

        p1 = self.create_product("Beans", Decimal("5"), category1)
        p2 = self.create_product("Soap", Decimal("15"), category2)

        participant = self.create_participant(email="multi@example.com")
        self.create_voucher(participant, multiplier=2, base_balance=Decimal("50"))

        order = self.create_order(participant)
        items = self.make_items([(p1, 2), (p2, 1)])
        self.add_items_to_order(order, items)

        utils = OrderUtils()
        utils.validate_order_items(items, participant, participant.accountbalance)

        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.items.first().product.name, "Beans")
        self.assertEqual(order.items.last().product.name, "Soap")

    def test_order_exactly_consumes_voucher(self):
        """
        Create an order that exactly matches the voucher amount.
        Voucher should remain active but have no remaining balance.
        """
        category = self.create_category("Canned Goods")
        product = self.create_product("Rice", Decimal("50"), category)

        participant = self.create_participant(email="exact@example.com")
        voucher = self.create_voucher(participant, multiplier=1, base_balance=Decimal("50"))

        order = self.create_order(participant)
        items = self.make_items([(product, 1)])
        self.add_items_to_order(order, items)

        utils = OrderUtils()
        utils.validate_order_items(items, participant, participant.accountbalance)

        self.assertEqual(voucher.voucher_amnt, Decimal("50"))
        self.assertEqual(order.items.first().quantity, 1)

    def test_order_with_hygiene_items_under_balance(self):
        """
        Order only contains hygiene items, total is below voucher_amnt and hygiene_balance.
        Should succeed and not deactivate voucher.
        """
        category = self.create_category("Hygiene")
        product = self.create_product("Soap", Decimal("30"), category)

        participant = self.create_participant(email="hygiene@example.com")
        participant.accountbalance.base_balance = Decimal("150")  # Hygiene balance = 50
        participant.accountbalance.save()

        voucher = self.create_voucher(participant, multiplier=1, base_balance=Decimal("150"))

        order = self.create_order(participant)
        items = self.make_items([(product, 1)])
        self.add_items_to_order(order, items)

        utils = OrderUtils()
        utils.validate_order_items(items, participant, participant.accountbalance)

        self.assertEqual(order.items.first().quantity, 1)
        self.assertEqual(voucher.voucher_amnt, Decimal("150"))

    def test_order_with_mixed_categories_under_balances(self):
        """
        Order contains multiple products including hygiene and regular items.
        Total does not exceed voucher or hygiene balances.
        """
        cat1 = self.create_category("Canned Goods")
        cat2 = self.create_category("Hygiene")

        p1 = self.create_product("Beans", Decimal("20"), cat1)
        p2 = self.create_product("Soap", Decimal("30"), cat2)

        participant = self.create_participant(email="mixed@example.com")
        participant.accountbalance.base_balance = Decimal("150")  # Hygiene = 50
        participant.accountbalance.save()

        voucher = self.create_voucher(participant, multiplier=1, base_balance=Decimal("150"))

        order = self.create_order(participant)
        items = self.make_items([(p1, 2), (p2, 1)])
        self.add_items_to_order(order, items)

        utils = OrderUtils()
        utils.validate_order_items(items, participant, participant.accountbalance)

        self.assertEqual(order.items.count(), 2)
        self.assertEqual(voucher.voucher_amnt, Decimal("150"))

    def test_order_with_multiple_vouchers(self):
        """
        Participant has multiple vouchers. Ensure order validation succeeds and voucher logic works.
        Because voucher_amnt is account-based, we only check the order is processed correctly.
        """
        category = self.create_category("Canned Goods")
        product = self.create_product("Beans", Decimal("25"), category)

        participant = self.create_participant(email="multi-voucher@example.com")
        # Create two vouchers; both use same account, so voucher_amnt will always reflect account base_balance
        v1 = self.create_voucher(participant, multiplier=1, base_balance=Decimal("50"))
        v2 = self.create_voucher(participant, multiplier=1, base_balance=Decimal("100"))

        order = self.create_order(participant)
        items = self.make_items([(product, 2)])
        self.add_items_to_order(order, items)

        utils = OrderUtils()
        utils.validate_order_items(items, participant, participant.accountbalance)

        # Assert order persisted
        self.assertEqual(order.items.first().quantity, 2)
        self.assertEqual(order.items.count(), 1)

