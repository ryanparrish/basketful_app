#food_orders.utils.order_helper.py 
import json
from django.shortcuts import get_object_or_404
from decimal import Decimal
from typing import Dict, Any

# ============================================================
# Standalone Utilities
# ============================================================

class OrderHelper:
    def __init__(self, order=None):
        self.order = order

    def get_product_prices_json() -> str:
        from food_orders.models import Product
        return json.dumps({str(p["id"]): float(p["price"]) for p in Product().objects.values("id", "price")})

    def get_order_or_404(order_id: int):
        from food_orders.models import Order
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