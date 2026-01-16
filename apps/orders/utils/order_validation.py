# food_orders.utils.order_validation.py
"""Utilities for validating orders and order items."""
from django.core.exceptions import ValidationError
from typing import List, Any
from dataclasses import dataclass
import logging
from .order_helper import OrderHelper
from apps.pantry.models import CategoryLimitValidator

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

        # Step 1: Validate category-level limits using CategoryLimitValidator
        CategoryLimitValidator.validate_category_limits(items, participant)

        # Step 2: Enforce hygiene balance
        OrderValidation.enforce_hygiene_balance(items, participant, account_balance)


