import logging
from django.forms.models import inlineformset_factory
from food_orders.forms import OrderItemInlineFormSet
from food_orders.models import (
    Product, Category, Participant, Order, OrderItem, Voucher
)

# ============================================================
# Shared Logger
# ============================================================
test_logger = logging.getLogger("food_orders_tests")
test_logger.setLevel(logging.INFO)

if not test_logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    test_logger.addHandler(handler)

# ============================================================
# Voucher Logging Utilities
# ============================================================
_logged_once = False  # module-level flag

def log_vouchers_for_account(account, context: str = "", order=None):
    """
    Logs all vouchers for a given account, including active/inactive state and totals.
    If an order is provided, logs order totals (including _test_price override).
    Can be reused across multiple test classes.
    """
    global _logged_once
    if not _logged_once:
        test_logger.info("\n === Starting Voucher Logging ===\n")
        _logged_once = True

    vouchers = Voucher.objects.filter(account=account)
    active_vouchers = [v for v in vouchers if v.active]
    inactive_vouchers = [v for v in vouchers if not v.active]

    test_logger.info(f"\n--- Voucher log: {context} ---")

    # Add order details if provided
    if order is not None:
        total_price = getattr(order, "_test_price", None)
        if total_price is None:
            try:
                total_price = order.total_price
            except Exception:
                total_price = "N/A"
        test_logger.info(
            f"Order ID: {getattr(order, 'id', 'unsaved')}, "
            f"Total Price={total_price}"
        )

    # Log each voucher
    for v in vouchers:
        test_logger.info(
            f"Voucher ID: {v.id}, Type: {v.voucher_type}, "
            f"Amount: {v.voucher_amnt}, Active: {v.active}"
        )

    total_balance = sum(v.voucher_amnt for v in active_vouchers)
    test_logger.info(
        f"Summary: Active={len(active_vouchers)}, "
        f"Inactive={len(inactive_vouchers)}, "
        f"Total Active Balance={total_balance}\n"
    )

    # Return for assertions if needed
    return {
        "active": active_vouchers,
        "inactive": inactive_vouchers,
        "total_balance": total_balance,
    }


# ============================================================
# Base Test Data Mixin
# ============================================================
class BaseTestDataMixin:
    """Helper methods to create test data for categories, products, participants, and orders."""

    def setUp(self):
        self.category_cb = self.create_category("Canned Goods")
        self.category_cr = self.create_category("Cereal")
        self.category_hygiene = self.create_category("Hygiene")

    # ---- Category ----
    def create_category(self, name: str) -> Category:
        return Category.objects.create(name=name)

    # ---- Product ----
    def create_product(
        self, name: str, price: float, category: Category,
        weight_lbs: float = 0.0, quantity: int = 10
    ) -> Product:
        return Product.objects.create(
            name=name,
            price=price,
            category=category,
            weight_lbs=weight_lbs,
            quantity_in_stock=quantity,
        )

    # ---- Participant ----
    def create_participant(self, **kwargs) -> Participant:
        defaults = {
            "name": "Test User",
            "email": "test@example.com",
            "adults": 2,
            "children": 1,
        }
        defaults.update(kwargs)
        return Participant.objects.create(**defaults)

    # ---- Order ----
    def create_order(self, account, status_type: str = "pending") -> Order:
        return Order.objects.create(account=account, status_type=status_type)

    # ---- Formset ----
    def get_formset(self, order: Order, data: dict):
        FormSet = inlineformset_factory(
            Order,
            OrderItem,
            formset=OrderItemInlineFormSet,
            fields=("product", "quantity", "price_at_order"),
            extra=1,
            can_delete=False,
        )
        return FormSet(data=data, instance=order, prefix="orderitem_set")

    # ---- Form data builder ----
    def build_form_data(self, product: Product, quantity: int) -> dict:
        return {
            "orderitem_set-TOTAL_FORMS": "1",
            "orderitem_set-INITIAL_FORMS": "0",
            "orderitem_set-MIN_NUM_FORMS": "0",
            "orderitem_set-MAX_NUM_FORMS": "1000",
            "orderitem_set-0-product": str(product.id),
            "orderitem_set-0-quantity": str(quantity),
            "orderitem_set-0-price_at_order": str(product.price),
        }

    def test_part_info(self, participant=None, context: str = ""):
        """
        Logs participant info for debugging.
        If no participant is passed, uses self.participant if it exists.
        """
        participant = participant or getattr(self, "participant", None)
        if not participant:
            test_logger.warning("No participant available to log.")
            return

        test_logger.info(
            f"Participant ID={participant.id}, Name={participant.name}, "
            f"Adults={participant.adults}, Children={participant.children}, "
            f"Infants/Diapers={participant.diaper_count} "
            f"{'| ' + context if context else ''}"
        )

