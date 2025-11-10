#food_orders.utils.order_helper.py 
import json
from django.shortcuts import get_object_or_404
from decimal import Decimal
from typing import Dict, Any
from ..models import Product
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)


# ============================================================
# Standalone Utilities
# ============================================================

class OrderHelper:
    def __init__(self, order=None):
        self.order = order

    @staticmethod
    def get_product_prices_json() -> str:
        products = Product.objects.values("id", "price")
        return json.dumps({str(p["id"]): float(p["price"]) for p in products})

    def get_order_or_404(order_id: int):
        from food_orders.models import Order
        return get_object_or_404(Order, pk=order_id)

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
    
    def _resolve_order_and_account(self, order, account_balance):
        """Ensure order and account_balance are provided and valid."""
        order = order or getattr(self, "order", None)
        
        if not order and not account_balance:
            raise ValidationError("Order or account_balance must be provided.")

        if not account_balance:
            account_balance = getattr(order, "account", None)

        if not account_balance or not hasattr(account_balance, "vouchers"):
            raise ValidationError("Order must have an associated AccountBalance with vouchers.")

        logger.debug(
            f"[Voucher Validator] Validating AccountBalance id={getattr(account_balance, 'id', None)}, "
            f"participant={getattr(account_balance, 'participant', None)}, "
            f"vouchers={list(account_balance.vouchers.values('id', 'state', 'active'))}"
        )
        return order, account_balance

    def _get_active_vouchers(self, account_balance):
        """Return all active (applied) vouchers for the given account."""
        return account_balance.vouchers.filter(state="applied")

    def _validate_voucher_presence(self, account_balance, active_vouchers):
        """Raise if no active vouchers are available."""
        if not active_vouchers.exists():
            participant = getattr(account_balance, "participant", None)
            raise ValidationError(f"[{participant}] Cannot confirm order: No vouchers applied to account.")

    def _validate_voucher_balance(self, account_balance, items, active_vouchers):
        """Ensure the order total does not exceed total voucher balance."""
        order_total = sum(item.product.price * item.quantity for item in items)
        total_voucher_balance = sum(v.voucher_amnt for v in active_vouchers)

        logger.debug(
            f"[Voucher Validator] Order total: {order_total}, "
            f"Total voucher balance: {total_voucher_balance}"
        )

        if order_total > total_voucher_balance:
            participant = getattr(account_balance, "participant", None)
            raise ValidationError(
                f"[{participant}] Order total ${order_total:.2f} exceeds available voucher balance "
                f"${total_voucher_balance:.2f}."
            )
    
  
