#food_orders.utils.order_utils.py 
"""Utility functions for managing food orders."""
import logging
from typing import List
from django.core.exceptions import ValidationError
from django.db import transaction
# First-party imports
from apps.orders.utils.order_validation import OrderItemData, OrderValidation

logger = logging.getLogger(__name__)


class OrderOrchestration:
    """Class to handle order operations like create, confirm, cancel, and clone."""
    def __init__(self, order=None):
        self.order = order

    # ----------------------------
    # Create Confirm, cancel, clone
    # ----------------------------
    @transaction.atomic
    def create_order(self, account, order_items_data: List['OrderItemData']):
        """Create a new order with the given account and order items."""
        from apps.orders.models import OrderItem
        from apps.orders.models import Order

        if not order_items_data:
            raise ValidationError("Cannot create an order with no items.")

        # Validate items
        order_validator = OrderValidation()
        participant = order_validator.validate_participant(account)
        order_validator.validate_order_items(order_items_data, participant, account)

        # Create the order
        order = Order.objects.create(account=account, status="pending")
        order.save() 

        # Bulk create order items
        items_bulk = [
            OrderItem(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.product.price,
                price_at_order=item.product.price,
            )
            for item in order_items_data
        ]

        if not items_bulk:
            raise ValidationError(f"Order must have at least one valid item.")

        OrderItem.objects.bulk_create(items_bulk)
        return order

    @transaction.atomic
    def confirm(self):
        """Confirm the order, setting its status to 'confirmed' and marking it as paid."""
        if not self.order:
            raise ValidationError("Order must be set before calling confirm()")
        if self.order.status == "confirmed":
            return 
        self.order.status = "confirmed"
        self.order.paid = True
        self.order.save(update_fields=["status", "updated_at"])
        logger.info("Order %s confirmed.", self.order.id)

    @transaction.atomic
    def cancel(self):
        """Cancel the order, setting its status to 'cancelled'."""
        if not self.order:
            raise ValueError("Order must be set before calling cancel()")
        self.order.status = "cancelled"
        self.order.save(update_fields=["status", "updated_at"])
        logger.info("Order %s cancelled.", self.order.id)

    @transaction.atomic
    def clone(self, status="pending"):
        """Clone the current order with a new status."""
        from apps.orders.models import OrderItem, Order

        if not self.order:
            raise ValueError("Order must be set before calling clone()")

        # Correct: use the class, not an instance
        new_order = Order.objects.create(
            account=self.order.account,
            status_type=status
        )

        # Now clone items from the original order
        # Important: DO NOT reassign self.order before iterating items
        items_to_clone = [
            OrderItem(
                order=new_order,
                product=item.product,
                quantity=item.quantity,
                price_at_order=getattr(item, "price_at_order", item.product.price),
                price=item.product.price,
            )
            for item in self.order.items.all()
        ]

        OrderItem.objects.bulk_create(items_to_clone)

        logger.info("Order %s cloned to %s with status '%s'.", self.order.id, new_order.id, status)

        # Now update self.order AFTER cloning
        self.order = new_order
        return new_order


