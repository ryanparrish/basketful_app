"""Order-related utility functions."""
# food_orders.utils.order_helper.py
import logging
from decimal import Decimal
import json
from typing import Dict, Any
# Django imports
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
# Local imports
from pantry.models import Product

logger = logging.getLogger(__name__)


# ============================================================
# Standalone Utilities
# ============================================================

class OrderHelper:
    def __init__(self, order=None):
        self.order = order

    @staticmethod
    def get_product_prices_json() -> str:
        """Return a JSON string mapping product IDs to their prices."""
        products = Product.objects.values("id", "price")
        return json.dumps({str(p["id"]): float(p["price"]) for p in products})

    def get_order_or_404(self, order_id: int):
        """Retrieve an Order by ID or raise 404 if not found."""
        from ..models import Order
        return get_object_or_404(Order, pk=order_id)

    def get_order_print_context(self, order) -> Dict[str, Any]:
        """Prepare context data for order printing."""
        participant = getattr(getattr(order, "account", None), "participant", None)
        return {
            "order": order,
            "items": order.items.select_related("product").all(),
            "total": getattr(order, "total_price()", lambda: 0)(),
            "customer": participant,
            "created_at": order.created_at,
        }

    def calculate_total_price(self, order) -> Decimal:
        """Calculate the total price of the order."""
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

    

  
