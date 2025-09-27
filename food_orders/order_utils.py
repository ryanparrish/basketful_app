import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List
from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.db import transaction
from django.apps import apps
import logging

logger = logging.getLogger("django.request")

logger = logging.getLogger(__name__)

# ============================================================
# Lazy model access functions
# ============================================================
def get_model(name: str):
    return apps.get_model('food_orders', name)

def Product():
    return get_model("Product")

def Order():
    return get_model("Order")

def OrderItem():
    return get_model("OrderItem")

def OrderValidationLog():
    return get_model("OrderValidationLog")

def AccountBalance():
    return get_model("AccountBalance")

# ============================================================
# Dataclass for order items
# ============================================================
@dataclass
class OrderItemData:
    product: Any
    quantity: int
    delete: bool = False

# ============================================================
# Order Utilities / Validators
# ============================================================
class OrderUtils:
    def __init__(self, order=None):
        self.order = order

    # ----------------------------
    # Participant validation
    # ----------------------------
    def validate_participant(self, account, user=None):
        participant = getattr(account, "participant", None)
        if not participant:
            raise ValidationError(None, "Account has no participant.")
        return participant

    # ----------------------------
    # Order items validation
    # ----------------------------

    def validate_order_items(
        self,
        items: List[OrderItemData],
        participant,
        account_balance,
        user=None,
    ):
        """
        Validate order items in the correct sequence:
        1. Category-level limits
        2. Hygiene balance
        3. Voucher balance
        """
        if not participant:
            logger.debug("[Validator] No participant found — skipping validation.")
            return

        logger.debug(f"[Validator] Validating for Participant: {participant}")

        # Step 1: Aggregate totals per category
        category_totals = {}   # category.id -> total value (weight or count)
        category_units = {}    # category.id -> 'lbs' or 'items'
        category_products = {} # category.id -> list of products (for logging)
        category_objects = {}  # category.id -> category object

        for item in items:
            product = item.product
            quantity = item.quantity

            if not product or not product.category:
                continue

            use_weight = getattr(product, "weight_lbs", 0) > 0
            value = quantity * getattr(product, "weight_lbs", 0) if use_weight else quantity
            category_id = product.category.id

            category_totals.setdefault(category_id, 0)
            category_units[category_id] = "lbs" if use_weight else "items"
            category_totals[category_id] += value

            category_products.setdefault(category_id, []).append(product)
            category_objects.setdefault(category_id, product.category)

        # Step 2: Enforce category-level limits
        for category_id, total_value in category_totals.items():
            category = category_objects[category_id]

            pm = getattr(category, "product_manager", None)
            if not pm or not pm.limit_scope or not pm.limit:
                continue

            allowed = pm.limit
            scope = pm.limit_scope
            unit = category_units[category_id]

            try:
                if scope == "per_adult":
                    allowed *= participant.adults
                elif scope == "per_child":
                    allowed *= participant.children
                elif scope == "per_infant":
                    # If no infants, allowed stays at 0 (no exception raised)
                    allowed *= participant.diaper_count or 0
                elif scope == "per_household":
                    allowed *= participant.household_size()
                elif scope == "per_order":
                    pass
            except Exception as e:
                logger.error(f"[Validator] Error computing allowed quantity: {e}")
                raise

            if total_value > allowed:
                product_names = ", ".join(p.name for p in category_products[category_id])
                msg = (
                    f"Category limit exceeded for {category.name} ({unit}, scope: {scope}): "
                    f"{total_value} > allowed {allowed}. Products: {product_names}"
                )
                raise ValidationError(f"[{participant}] {msg}")

        # Step 3: Hygiene balance check
        OrderUtils.enforce_hygiene_balance(items, participant, account_balance)

    # --------------------
    # Static helpers
    # --------------------

    @staticmethod
    def calculate_order_total(items):
        """Calculate total cost of all items in the order."""
        return sum(item.product.price * item.quantity for item in items)

    @staticmethod
    def calculate_hygiene_total(items):
        """Calculate the total cost of hygiene items in the order."""
        return sum(
            item.product.price * item.quantity
            for item in items
            if item.product.category.name.lower() == "hygiene"
        )

    @staticmethod
    def enforce_hygiene_balance(items, participant, account_balance):
        """Ensure hygiene items do not exceed the participant’s hygiene balance."""
        hygiene_total = OrderUtils.calculate_hygiene_total(items)
        hygiene_balance = getattr(account_balance, "hygiene_balance", 0)

        if hygiene_total > hygiene_balance:
            msg = (
                f"Hygiene items total ${hygiene_total:.2f}, "
                f"exceeds hygiene balance ${hygiene_balance:.2f}."
            )
            raise ValidationError(f"[{participant}] {msg}")

    # ----------------------------
    # Voucher validation
    # ----------------------------
    def validate_order_vouchers(self, order=None, items=None):
        """
        Ensure order can be confirmed:
        1. Account has active vouchers
        2. Order total does not exceed available voucher balance
        """
        order = order or getattr(self, "order", None)
        if not order:
            raise ValidationError("Order must be provided or set on self.")

        status = str(getattr(order, "status_type", "")).lower()
        if status != "confirmed":
            return  # No validation needed

        account = getattr(order, "account", None)
        if not account:
            raise ValidationError("Order must have an associated account.")

        active_vouchers = account.vouchers.filter(active=True)
        if not active_vouchers.exists():
            raise ValidationError("Cannot confirm order: no active vouchers available")

        # If items are provided, check that total does not exceed voucher balance
        if items:
            order_total = self.calculate_order_total(items)
            total_voucher_balance = sum(v.voucher_amnt for v in active_vouchers)
            if order_total > total_voucher_balance:
                participant = getattr(account, "participant", None)
                msg = (
                    f"Order total ${order_total:.2f} exceeds available voucher balance "
                    f"${total_voucher_balance:.2f}."
                )
                raise ValidationError(f"[{participant}] {msg}")

    # ----------------------------
    # Confirm, cancel, clone
    # ----------------------------
    @transaction.atomic
    def confirm(self):
        if not self.order:
            raise ValueError("Order must be set before calling confirm()")
        self.validate_order_items(
        [OrderItemData(item.product, item.quantity) for item in self.order.items.all()],
        getattr(self.order.account, "participant", None),
        self.order.account, 
        user=getattr(self.order.account.participant, "user", None)
)
        self.order.status_type = "confirmed"
        self.order.save(update_fields=["status_type", "updated_at"])
        self.validate_order_vouchers()
        logger.info(f"Order {self.order.id} confirmed.")

    @transaction.atomic
    def cancel(self):
        if not self.order:
            raise ValueError("Order must be set before calling cancel()")
        self.order.status_type = "cancelled"
        self.order.save(update_fields=["status_type", "updated_at"])
        logger.info(f"Order {self.order.id} cancelled.")

    @transaction.atomic
    def clone(self, status="pending"):
        if not self.order:
            raise ValueError("Order must be set before calling clone()")
        new_order = Order().objects.create(account=self.order.account, status_type=status)
        self.order = new_order

        items_to_clone = [
            OrderItem()(
                order=new_order,
                product=item.product,
                quantity=item.quantity,
                price_at_order=getattr(item, "price_at_order", item.product.price),
                price=item.product.price,
            )
            for item in self.order.items.all()
        ]
        OrderItem().objects.bulk_create(items_to_clone)
        logger.info(f"Order {self.order.id} cloned to {new_order.id} with status '{status}'.")
        return new_order

    # ----------------------------
    # Create order
    # ----------------------------
    @transaction.atomic
    def create_order(self, account, order_items_data: List[OrderItemData]):
        participant = self.validate_participant(account)
        user_for_logging = getattr(participant, "user", None)
        if not order_items_data:
            raise ValidationError(f"[{participant}] Cannot create an order with no items")
            
        self.validate_order_items(order_items_data, participant, account, user_for_logging)
        order = Order().objects.create(account=account, status_type="pending")
        self.order = order

        items_bulk = [
            OrderItem()(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.product.price,
                price_at_order=item.product.price,
            )
            for item in order_items_data
            ]

        if not items_bulk:
            raise ValidationError(f"[{participant}] Order must have at least one valid item.", )

        OrderItem().objects.bulk_create(items_bulk)
        self.confirm()
        return order
# ============================================================
# Standalone Utilities
# ============================================================
def get_product_prices_json() -> str:
    return json.dumps({str(p["id"]): float(p["price"]) for p in Product().objects.values("id", "price")})

def get_order_or_404(order_id: int):
    return get_object_or_404(Order(), pk=order_id)

def get_order_print_context(order) -> Dict[str, Any]:
    participant = getattr(getattr(order, "account", None), "participant", None)
    return {
        "order": order,
        "items": order.items.select_related("product").all(),
        "total": getattr(order, "total_price", lambda: 0)(),
        "customer": participant,
        "created_at": order.created_at,
    }

def calculate_total_price(order) -> Decimal:
    if hasattr(order, "_test_price"):
        return Decimal(order._test_price)
    total = Decimal(0)
    for item in order.items.all():
        price = item.price_at_order or Decimal(0)
        quantity = item.quantity or 0
        total += price * quantity
    return total
