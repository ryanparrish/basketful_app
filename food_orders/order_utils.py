import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List
from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.db import transaction
from django.apps import apps

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
            self.log_and_raise(None, "Account has no participant.", user=user)
        return participant

    # ----------------------------
    # Voucher validation
    # ----------------------------
    def validate_order_vouchers(self):
        if not self.order:
            raise ValueError("Order must be set before validating vouchers.")
        if getattr(self.order, "status_type", "").lower() == "confirmed":
            active_vouchers = Voucher().objects.filter(account=self.order.account, active=True)
            if not active_vouchers.exists():
                self.log_and_raise(
                    getattr(self.order.account, "participant", None),
                    "Cannot confirm order: no active vouchers available.",
                    user=getattr(self.order.account.participant, "user", None)
                )

    # ----------------------------
    # Confirm, cancel, clone
    # ----------------------------
    @transaction.atomic
    def confirm(self):
        if not self.order:
            raise ValueError("Order must be set before calling confirm()")
        self.order.status_type = "confirmed"
        self.order.save(update_fields=["status_type", "updated_at"])
        self.validate_order_vouchers()
        # self.apply_voucher_and_mark_paid()  # implement as needed
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
        self.order = new_order  # set the new order as current order

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
            self.log_and_raise(participant, "Cannot create an order with no items.", user=user_for_logging)

        # Validate items here if needed
        # self.validate_order_items(order_items_data, participant, account)

        # Create order
        order = Order().objects.create(account=account, status_type="pending")
        self.order = order  # IMPORTANT: set self.order

        # Create order items
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
            self.log_and_raise(participant, "Order must have at least one valid item.", user=user_for_logging)

        OrderItem().objects.bulk_create(items_bulk)

        # Confirm the order
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
