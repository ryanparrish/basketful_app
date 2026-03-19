# food_orders.utils.order_utils.py
"""Utility functions for managing food orders."""
import logging
import json
from typing import List, Optional, Dict, Any
from apps.orders.types import CartItem, OrderError
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.contrib.auth import get_user_model

# First-party imports
from apps.orders.utils.order_validation import OrderItemData, OrderValidation
from apps.orders.utils.order_services import (
    generate_idempotency_key,
    generate_cart_hash,
    distributed_order_lock,
    check_duplicate_submission,
)
from apps.orders.api.throttles import reset_failure_count, increment_failure_count

User = get_user_model()
logger = logging.getLogger(__name__)


class OrderOrchestration:
    """Class to handle order operations like create, confirm, cancel, and clone."""
    def __init__(self, order=None):
        self.order = order

    # ----------------------------
    # Create Confirm, cancel, clone
    # ----------------------------
    def create_order(
        self,
        account,
        order_items_data: List['OrderItemData'],
        user: Optional[User] = None,
        request_meta: Optional[Dict[str, Any]] = None
    ):
        """
        Create a new order with validation-first approach.
        
        This method:
        1. Validates all constraints BEFORE creating any DB records
        2. Uses distributed lock to prevent race conditions
        3. Checks idempotency to prevent duplicates
        4. Logs failed attempts with full context
        5. Only creates Order record if validation passes
        
        Args:
            account: The participant's account
            order_items_data: List of OrderItemData objects
            user: Optional User making the request (for audit)
            request_meta: Optional dict with 'ip' and 'user_agent' for audit
        
        Returns:
            Order: The created order instance
            
        Raises:
            ValidationError: If any validation fails
        """
        from apps.orders.models import OrderItem, Order, FailedOrderAttempt
        from apps.pantry.models import Product
        
        if not order_items_data:
            raise ValidationError("Cannot create an order with no items.")
        
        # Extract request metadata
        ip_address = None
        user_agent = None
        if request_meta:
            ip_address = request_meta.get('ip')
            user_agent = request_meta.get('user_agent')
        
        # Generate idempotency key and cart hash
        cart_dict = [
            {'product_id': item.product.id, 'quantity': item.quantity}
            for item in order_items_data
        ]
        idempotency_key = generate_idempotency_key(account.participant.id, cart_dict)
        cart_hash = generate_cart_hash(cart_dict)

        # Build enriched snapshot separately (product names + prices for debugging)
        cart_snapshot: List[CartItem] = [
            {
                'product_id': item.product.id,
                'product_name': item.product.name,
                'quantity': item.quantity,
                'price': str(item.product.price),
            }
            for item in order_items_data
        ]
        
        # Check for duplicate submission
        if check_duplicate_submission(idempotency_key):
            error_msg = "Duplicate order submission detected. Please wait before retrying."
            logger.warning(
                f"Duplicate submission for participant {account.participant.id}: "
                f"{idempotency_key}"
            )
            
            # Increment failure count (causes exponential backoff)
            if user:
                increment_failure_count(user.id)
            
            raise ValidationError(error_msg)
        
        # Precompute totals for failed-attempt logging.
        food_total = Decimal('0.00')
        hygiene_total = Decimal('0.00')
        for item in order_items_data:
            item_total = item.product.price * item.quantity
            category_name = getattr(item.product.category, 'name', '').lower()
            if category_name == 'hygiene':
                hygiene_total += item_total
            else:
                food_total += item_total
        total_attempted = food_total + hygiene_total

        # Acquire distributed lock
        with distributed_order_lock(account.participant.id, timeout=10) as lock_acquired:
            if not lock_acquired:
                error_msg = (
                    "Another order is being processed. Please wait a moment and try again."
                )
                logger.warning(
                    f"Failed to acquire lock for participant {account.participant.id}"
                )
                
                # Increment failure count
                if user:
                    increment_failure_count(user.id)
                
                raise ValidationError(error_msg)
            
            try:
                # STEP 1: Validate participant and items (NO DB WRITES YET)
                order_validator = OrderValidation()
                participant = order_validator.validate_participant(account)
                
                # This validates all constraints: balance, hygiene, categories, vouchers
                order_validator.validate_order_items(
                    order_items_data, participant, account
                )
                
                # Get active pause details for tracking
                from apps.pantry.models import CategoryLimitValidator
                pause_multiplier, pause_name = CategoryLimitValidator._get_active_pause_multiplier()
                
                # STEP 2: All validation passed - create Order and items atomically.
                with transaction.atomic():
                    order = Order.objects.create(
                        account=account, 
                        status="pending",
                        program_pause_at_creation=pause_name if pause_multiplier > 1 else None,
                        pause_multiplier_at_creation=pause_multiplier if pause_multiplier > 1 else None
                    )
                    order.save()

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
                        raise ValidationError("Order must have at least one valid item.")

                    OrderItem.objects.bulk_create(items_bulk)
                
                # STEP 4: Reset failure count on success
                if user:
                    reset_failure_count(user.id)
                
                logger.info(
                    f"Order {order.order_number} created successfully for "
                    f"participant {account.participant.id}"
                )
                
                return order
                
            except ValidationError as e:
                # STEP 5: Log failed attempt with full context
                # Normalise to a consistent list-of-dicts format so the
                # frontend analytics widget can always rely on the same shape.
                error_messages: List[OrderError]
                if hasattr(e, 'message_dict'):
                    error_messages = [
                        {'type': field, 'message': msg}
                        for field, msgs in e.message_dict.items()
                        for msg in (msgs if isinstance(msgs, list) else [msgs])
                    ]
                elif hasattr(e, 'messages'):
                    error_messages = [
                        {'type': 'validation', 'message': str(m)}
                        for m in e.messages
                    ]
                else:
                    error_messages = [{'type': 'validation', 'message': str(e)}]
                error_summary = str(e)
                participant = getattr(account, "participant", None)
                
                # Get program pause info
                program_pause_active = False
                program_pause_name = ""
                voucher_multiplier = 1
                
                try:
                    from apps.voucher.models import Voucher
                    pause_voucher = Voucher.objects.filter(
                        account=account,
                        active=True,
                        program_pause_flag=True,
                    ).order_by("-multiplier").first()
                    
                    if pause_voucher:
                        program_pause_active = True
                        voucher_multiplier = pause_voucher.multiplier
                        try:
                            program_pause_name = (
                                pause_voucher.account.participant.program.name
                            )
                        except Exception:
                            program_pause_name = "Active Program Pause"
                except Exception as pause_err:
                    logger.error(f"Error getting program pause info: {pause_err}")
                
                # Count active vouchers
                active_voucher_count = 0
                try:
                    from apps.voucher.models import Voucher
                    active_voucher_count = Voucher.objects.filter(
                        account=account,
                        active=True,
                        state='applied'
                    ).count()
                except Exception as voucher_err:
                    logger.error(f"Error counting vouchers: {voucher_err}")
                
                # Create failed attempt record.
                # The idempotency_key field is unique — if the same failing cart
                # is retried within the same minute it would cause an IntegrityError
                # and silently drop the second log entry.  Append a short random
                # suffix so every failed attempt is always recorded.
                # Truncate base key to ensure unique_fail_key fits in 64 chars.
                import secrets as _secrets
                random_suffix = _secrets.token_hex(4)  # 8 chars
                # Reserve 9 chars for ":{suffix}", leave 55 for base key
                base_key = idempotency_key[:55] if len(idempotency_key) > 55 else idempotency_key
                unique_fail_key = f"{base_key}:{random_suffix}"
                try:
                    FailedOrderAttempt.objects.create(
                        participant=participant,
                        user=user,
                        idempotency_key=unique_fail_key,
                        cart_snapshot=cart_snapshot,
                        cart_hash=cart_hash,
                        total_attempted=total_attempted,
                        food_total=food_total,
                        hygiene_total=hygiene_total,
                        full_balance=account.full_balance,
                        available_balance=account.available_balance,
                        hygiene_balance=account.hygiene_balance,
                        program_pause_active=program_pause_active,
                        program_pause_name=program_pause_name,
                        voucher_multiplier=voucher_multiplier,
                        active_voucher_count=active_voucher_count,
                        validation_errors=error_messages,
                        error_summary=error_summary,
                        ip_address=ip_address,
                        user_agent=user_agent,
                    )
                    logger.info(
                        f"Logged failed order attempt for participant {participant.id if participant else 'unknown'}: "
                        f"{error_summary}"
                    )
                except Exception as log_err:
                    logger.error(f"Failed to log order attempt: {log_err}")
                
                # Increment failure count (triggers exponential backoff)
                if user:
                    increment_failure_count(user.id)
                
                # Re-raise the original validation error
                raise

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
