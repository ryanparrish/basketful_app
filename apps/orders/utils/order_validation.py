#food_orders.utils.order_validation.py 
"""Utilities for validating orders and order items."""
from django.core.exceptions import ValidationError
from typing import List, Any
from dataclasses import dataclass
import logging
from .order_helper import OrderHelper

logger = logging.getLogger(__name__)


@dataclass
class OrderItemData:
    """Data class representing an order item for validation purposes."""
    product: Any
    quantity: int
    delete: bool = False


class OrderValidation:
    """Class for validating orders and their items."""
    def __init__(self, order=None):
        self.order = order

    def validate_participant(self, account, user=None):
        """Validate that the account has an associated participant."""
        participant = getattr(account, "participant", None)
        if not participant:
            raise ValidationError(None, "Account has no participant.")
        return participant
  
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

        logger.debug("[Validator] Validating for Participant: %s", participant)

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
        """
        Check each category and subcategory's total against its configured
        limit.
        """
        for category_id, total_value in category_totals.items():
            category_or_subcategory = category_objects[category_id]

            # Fetch limits for subcategories or categories
            if hasattr(category_or_subcategory, "subcategory_limits"):
                limits = category_or_subcategory.subcategory_limits.all()
            elif hasattr(category_or_subcategory, "category_limits"):
                limits = category_or_subcategory.category_limits.all()
            else:
                continue

            for limit in limits:
                allowed = self._compute_allowed_quantity(limit, participant)
                unit = category_units[category_id]

                if total_value > allowed:
                    product_names = ", ".join(
                        p.name for p in category_products[category_id]
                    )
                    msg = (
                        f"Limit exceeded for {category_or_subcategory.name} "
                        f"({unit}, scope: {limit.limit_scope}): "
                        f"{total_value} > allowed {allowed}. "
                        f"Products: {product_names}"
                    )
                    raise ValidationError(f"[{participant}] {msg}")

                logger.debug(
                    f"[Validator] {category_or_subcategory.name}: "
                    f"total={total_value}, allowed={allowed}, "
                    f"scope={limit.limit_scope} ({unit})"
                )

