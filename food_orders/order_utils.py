import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List
from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.db import transaction
from django.apps import apps
from django.core.exceptions import ValidationError
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

def Voucher():
    return get_model("Voucher")

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
    # Logging and error handling
    # ----------------------------
    def log_and_raise(self, participant, message: str, product=None, user=None):
        OrderValidationLog().objects.create(
            participant=participant,
            product=product,
            message=message,
            user=user
        )
        logger.warning(f"[Validator] {message}")
        raise ValidationError(message)

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
        Validate order items at the category level.
        Enforces limits per category (weighted or count-based),
        hygiene balance, and voucher balance (via Voucher.voucher_amnt).
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
                    if participant.diaper_count == 0:
                        raise ValidationError(
                        participant, f"Limit is per infant, but participant has none in category {category.name}.",
                        )
                    allowed *= participant.diaper_count
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
                raise ValidationError (participant, msg)

        # Step 3: Compute line totals for hygiene and voucher checks
        hygiene_total = sum(
            item.product.price * item.quantity
            for item in items
            if item.product.category.name.lower() == "hygiene"
        )
        order_total = sum(item.product.price * item.quantity for item in items)

        # Step 4: Hygiene balance check
        if hygiene_total > getattr(account_balance, "hygiene_balance", 0):
            msg = (
                f"Hygiene items total ${hygiene_total:.2f}, exceeds hygiene balance "
                f"${getattr(account_balance, 'hygiene_balance', 0):.2f}."
            )
            raise ValidationError (participant, msg)

        # Step 5: Voucher balance check (dynamic via vouchers)
        total_voucher_balance = sum(
            v.voucher_amnt for v in account_balance.vouchers.filter(active=True)
        )

        if order_total > total_voucher_balance:
            msg = (
                f"Order total ${order_total:.2f} exceeds available voucher balance "
                f"${total_voucher_balance:.2f}."
            )
            raise ValidationError(participant, msg)

        logger.debug("[Validator] Category-level validation completed successfully.")

    # ----------------------------
    # Voucher validation
    # ----------------------------

    def validate_order_vouchers(self, order=None):
        order = order or getattr(self, "order", None)
        if not order:
            raise ValidationError("Order must be provided or set on self.")

        status = str(getattr(order, "status_type", "")).lower()
        if status != "confirmed":
            return  # No validation needed

        account = getattr(order, "account", None)
        if not account:
            raise ValidationError("Order must have an associated account.")

        if not Voucher.objects.filter(account=account, active=True).exists():
            
        # Raise ValidationError for enforcement
            raise ValidationError("Cannot confirm order: no active vouchers available")

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
        self.order.account, # Pass the entire account object here
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
            raise ValidationError(participant, "Cannot create an order with no items")

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
            raise ValidationError(participant, "Order must have at least one valid item.", )

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
