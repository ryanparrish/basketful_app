#food_orders.utils.order_utils.py 
import logging
from typing import List
from django.core.exceptions import ValidationError
from django.db import transaction
from .order_validation import OrderItemData, OrderValidation

logger = logging.getLogger(__name__)

class OrderOrchestration:
    def __init__(self, order=None):
        self.order = order

    # ----------------------------
    # Create Confirm, cancel, clone
    # ----------------------------
    @transaction.atomic
    def create_order(self, account, order_items_data: List['OrderItemData']):
        from food_orders.models import OrderItem, Order

        if not order_items_data:
            raise ValidationError(f"Cannot create an order with no items.")

        # Validate items
        order_validator = OrderValidation()
        participant = order_validator.validate_participant(account)
        order_validator.validate_order_items(order_items_data, participant, account)

        # Create the order
        order = Order.objects.create(account=account, status_type="pending")
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
        if not self.order:
            raise ValidationError("Order must be set before calling confirm()")
        if self.order.status_type == "confirmed":
            return 
        self.order.status_type = "confirmed"
        self.order.save(update_fields=["status_type", "updated_at"])
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
        from food_orders.models import OrderItem, Order

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

        logger.info(f"Order {self.order.id} cloned to {new_order.id} with status '{status}'.")

        # Now update self.order AFTER cloning
        self.order = new_order
        return new_order


