#food_orders.utils.order_validation.py 
from django.core.exceptions import ValidationError
from typing import List, Any
from dataclasses import dataclass
import logging
from .order_helper import OrderHelper

logger = logging.getLogger(__name__)

@dataclass
class OrderItemData:
    product: Any
    quantity: int
    delete: bool = False

class OrderValidation:
    def __init__(self, order=None):
        self.order = order

    def validate_participant(self, account, user=None):
        participant = getattr(account, "participant", None)
        if not participant:
            raise ValidationError(None, "Account has no participant.")
        return participant
    
    def validate_order_vouchers(self, order=None, items=None, account_balance=None):
        """
         Validate that an order can safely be confirmed:
        1. The AccountBalance has active vouchers.
        2. The order total does not exceed available voucher balance.

        Note: This should be called **before** setting order.status_type = "confirmed".
        Voucher application happens automatically in Order.save().
        """
        helper = OrderHelper(order)
        order, account_balance = helper._resolve_order_and_account(order, account_balance)
        active_vouchers = helper._get_active_vouchers(account_balance)
        helper._validate_voucher_presence(account_balance, active_vouchers)
        if items:
            helper._validate_voucher_balance(account_balance, items, active_vouchers)

        logger.info(
            f"[Voucher Validator] Order {getattr(order, 'id', None)}passed voucher validation.")

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
        (
            category_totals,
            category_units,
            category_products,
            category_objects,
        ) = self._aggregate_category_data(items)

        # Step 2: Enforce category-level limits
        self._enforce_category_limits(
            participant,
            category_totals,
            category_units,
            category_products,
            category_objects,
        )

        OrderValidation.enforce_hygiene_balance(items, participant, account_balance)

        self.validate_order_vouchers(items=items, account_balance=account_balance)
    def _aggregate_category_data(self, items: list):
        """
        Aggregate order items by their category or subcategory based on model relationships.

        - If a product has a subcategory, it groups by subcategory.
        - Otherwise, it groups by category.
        """

        category_totals = {}
        category_units = {}
        category_products = {}
        category_objects = {}

        for item_data in items:
            if getattr(item_data, "delete", False):
                continue

            product = getattr(item_data, "product", None)
            quantity = getattr(item_data, "quantity", 0)
            if not product:
                continue

            # Check relationships
            subcategory = getattr(product, "subcategory", None)
            category = getattr(product, "category", None)

            # Determine grouping object and level
            if subcategory and category:
                obj = subcategory  # subcategory-level enforcement
            elif category:
                obj = category     # category-level enforcement
            else:
                continue  # skip if neither is defined

            cid = obj.id
            category_totals[cid] = category_totals.get(cid, 0) + quantity
            category_units[cid] = getattr(obj, "unit", getattr(category, "unit", "unit"))
            category_products.setdefault(cid, []).append(product)
            category_objects[cid] = obj

        return category_totals, category_units, category_products, category_objects

    def _compute_allowed_quantity(self, product_manager, participant):

        """Compute allowed quantity based on the category's limit scope."""
        allowed = product_manager.limit
        scope = product_manager.limit_scope

        try:
            if scope == "per_adult":
                allowed *= participant.adults
            elif scope == "per_child":
                allowed *= participant.children
            elif scope == "per_infant":
                allowed *= participant.diaper_count or 0
            elif scope == "per_household":
                allowed *= participant.household_size()
            elif scope == "per_order":
                pass
        except Exception as e:
            logger.error(f"[Validator] Error computing allowed quantity: {e}")
            raise ValidationError("Error computing allowed quantity")
        return allowed
    
    def _enforce_category_limits(
        self,
        participant,
        category_totals,
        category_units,
        category_products,
        category_objects,
    ):
        """Check each category's total against its configured limit."""
        for category_id, total_value in category_totals.items():
            category = category_objects[category_id]
            pm = getattr(category, "product_manager", None)

            if not pm or not pm.limit_scope or not pm.limit:
                continue

            allowed = self._compute_allowed_quantity(pm, participant)
            unit = category_units[category_id]

            if total_value > allowed:
                product_names = ", ".join(p.name for p in category_products[category_id])
                msg = (
                    f"Category limit exceeded for {category.name} ({unit}, scope: {pm.limit_scope}): "
                    f"{total_value} > allowed {allowed}. Products: {product_names}"
                )
                raise ValidationError(f"[{participant}] {msg}")

            logger.debug(f"[Validator] {category.name}: total={total_value}, allowed={allowed}, scope={pm.limit_scope} ({unit})")

