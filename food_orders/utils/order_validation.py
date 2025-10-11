#food_orders.utils.order_validation.py 
from django.core.exceptions import ValidationError
from typing import List, Any
from dataclasses import dataclass
import logging
from .order_helper import OrderHelper

logger = logging.getLogger(__name__)

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
class OrderValidation:
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
    # Voucher validation
    # ----------------------------
    def validate_order_vouchers(self, order=None, items=None, account_balance=None):
        """
        Validate that an order can safely be confirmed:
        1. The AccountBalance has active vouchers.
        2. The order total does not exceed available voucher balance.

        Note: This should be called **before** setting order.status_type = "confirmed".
        Voucher application happens automatically in Order.save().
        """
        order = order or getattr(self, "order", None)

        if not order and not account_balance:
            raise ValidationError("Order or account_balance must be provided.")

        # Resolve the AccountBalance
        if not account_balance:
            account_balance = getattr(order, "account", None)
        if not account_balance or not hasattr(account_balance, "vouchers"):
            raise ValidationError("Order must have an associated AccountBalance with vouchers.")
        
        # DEBUG: show vouchers linked to this account_balance
        logger.debug(
            f"[Voucher Validator] Validating AccountBalance id={getattr(account_balance, 'id', None)}, "
            f"participant={getattr(account_balance, 'participant', None)}, "
            f"vouchers={list(account_balance.vouchers.values('id','state','active'))}"
            )
        # Skip validation if there are no vouchers at all
        active_vouchers = account_balance.vouchers.filter(state="applied")
        if not active_vouchers.exists():
            participant = getattr(account_balance, "participant", None)
            raise ValidationError(f"[{participant}] Cannot confirm order: No vouchers applied to account.")

        # If items are provided, check that total does not exceed available voucher balance
        if items:
            order_total = sum(item.product.price * item.quantity for item in items)
            total_voucher_balance = sum(v.voucher_amnt for v in active_vouchers)

            logger.debug(
                f"[Voucher Validator] Order total: {order_total}, Total voucher balance: {total_voucher_balance}"
            )

            if order_total > total_voucher_balance:
                participant = getattr(account_balance, "participant", None)
                raise ValidationError(
                    f"[{participant}] Order total ${order_total:.2f} exceeds available voucher balance "
                    f"${total_voucher_balance:.2f}."
                )

        logger.info(f"[Voucher Validator] Order {getattr(order, 'id', None)} passed voucher validation.")

    @staticmethod
    def enforce_hygiene_balance(items, participant, account_balance):
        """Ensure hygiene items do not exceed the participant’s hygiene balance."""
        hygiene_total = OrderHelper.calculate_hygiene_total(items)
        hygiene_balance = getattr(account_balance, "hygiene_balance", 0)

        if hygiene_total > hygiene_balance:
            msg = (
                f"Hygiene items total ${hygiene_total:.2f}, "
                f"exceeds hygiene balance ${hygiene_balance:.2f}."
            )
            raise ValidationError(f"[{participant}] {msg}")
        
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
                raise ValidationError ( "Error computing allowed quantity")

            if total_value > allowed:
                product_names = ", ".join(p.name for p in category_products[category_id])
                msg = (
                    f"Category limit exceeded for {category.name} ({unit}, scope: {scope}): "
                    f"{total_value} > allowed {allowed}. Products: {product_names}"
                )
                raise ValidationError(f"[{participant}] {msg}")

        # Step 3: Hygiene balance check
        OrderValidation.enforce_hygiene_balance(items, participant, account_balance)