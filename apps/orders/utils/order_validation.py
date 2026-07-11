# food_orders.utils.order_validation.py
"""Utilities for validating orders and order items."""
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
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
            msg = _(
                "Hygiene items total $%(total)s, "
                "exceeds hygiene balance $%(balance)s."
            ) % {
                'total': f"{hygiene_total:.2f}",
                'balance': f"{hygiene_balance:.2f}",
            }
            raise ValidationError(f"[{participant}] {msg}")

    @staticmethod
    def enforce_program_pause(participant):
        """Block ordering while a program pause is in progress (Issue #78).

        The pause week is a no-order week for all programs. An unexpired
        force-open ProgramWindowOverride on the participant's program is
        the staff escape hatch — it lets orders through even mid-pause.
        """
        from core.utils import get_active_window_override, get_in_progress_pause

        in_progress_pause = get_in_progress_pause()
        if not in_progress_pause:
            return

        program = getattr(participant, 'program', None)
        if program is not None:
            override = get_active_window_override(program)
            if override and override.force_status == 'open':
                logger.info(
                    "[Validator] %s - pause in progress but force-open "
                    "override active for program %s; allowing order",
                    participant, program,
                )
                return

        from django.utils import formats
        msg = _(
            "Ordering is unavailable during the program pause. "
            "Orders reopen after %(pause_end)s."
        ) % {'pause_end': formats.date_format(in_progress_pause.pause_end, 'DATE_FORMAT')}
        logger.warning(
            "[Validator] %s - order blocked: program pause in progress "
            "(%s to %s)",
            participant,
            in_progress_pause.pause_start,
            in_progress_pause.pause_end,
        )
        raise ValidationError(msg)

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
        0. Program pause (ordering blocked during the off week)
        1. Category-level limits
        2. Hygiene balance
        3. Voucher balance
        """
        if not participant:
            logger.debug("[Validator] No participant found — skipping validation.")
            return

        logger.debug("[Validator] Validating for Participant: %s", participant)

        # Step 0: Block ordering entirely while a program pause is in progress
        OrderValidation.enforce_program_pause(participant)

        # Step 1: Validate category-level limits using CategoryLimitValidator
        CategoryLimitValidator.validate_category_limits(items, participant)

        # Step 2: Enforce hygiene balance
        OrderValidation.enforce_hygiene_balance(items, participant, account_balance)

        # Step 3: Validate available balance for food items (non-hygiene)
        food_items = [
            item for item in items
            if getattr(item.product.category, "name", "").lower() != "hygiene"
        ]
        food_total = sum(item.product.price * item.quantity for item in food_items)
        available_balance = getattr(account_balance, "available_balance", 0)

        if food_total > available_balance:
            msg = _(
                "Food items total $%(total)s exceeds available voucher "
                "balance $%(balance)s."
            ) % {
                'total': f"{food_total:.2f}",
                'balance': f"{available_balance:.2f}",
            }
            logger.warning("[Validator] %s - Food total exceeds balance", participant)
            raise ValidationError(f"[{participant}] {msg}")

        # Step 3b: Validate combined food + hygiene total against voucher balance.
        # hygiene_balance is a sub-limit (available_balance / 3).  An order can
        # pass each individual check yet still exceed the voucher pool — e.g.
        # food=$132.50 ≤ $135 and hygiene=$24.50 ≤ $45, but combined=$157 > $135.
        hygiene_items = [
            item for item in items
            if getattr(item.product.category, "name", "").lower() == "hygiene"
        ]
        hygiene_total = sum(item.product.price * item.quantity for item in hygiene_items)
        combined_total = food_total + hygiene_total
        if combined_total > available_balance:
            msg = _(
                "Food and hygiene items total $%(total)s exceeds "
                "available voucher balance $%(balance)s."
            ) % {
                'total': f"{combined_total:.2f}",
                'balance': f"{available_balance:.2f}",
            }
            logger.warning("[Validator] %s - Combined food+hygiene total exceeds balance", participant)
            raise ValidationError(f"[{participant}] {msg}")

        # Step 4: Validate Go Fresh balance (if enabled)
        go_fresh_balance = getattr(account_balance, "go_fresh_balance", 0)
        if go_fresh_balance > 0:
            go_fresh_items = [
                item for item in items
                if item.product.category and item.product.category.name.lower() == "go fresh"
            ]
            go_fresh_total = sum(item.product.price * item.quantity for item in go_fresh_items)
            
            if go_fresh_total > go_fresh_balance:
                msg = _(
                    "Go Fresh items total $%(total)s exceeds Go Fresh "
                    "balance $%(balance)s."
                ) % {
                    'total': f"{go_fresh_total:.2f}",
                    'balance': f"{go_fresh_balance:.2f}",
                }
                logger.warning("[Validator] %s - Go Fresh total exceeds balance", participant)
                raise ValidationError(f"[{participant}] {msg}")

        # Step 5: Validate stock availability — prevent confirming orders for out-of-stock items.
        out_of_stock = []
        for item in items:
            available = getattr(item.product, 'quantity_in_stock', None)
            if available is not None and available < item.quantity:
                out_of_stock.append(
                    _("%(product)s: requested %(requested)d, only %(available)d in stock") % {
                        'product': item.product.name,
                        'requested': item.quantity,
                        'available': available,
                    }
                )
        if out_of_stock:
            detail = "; ".join(out_of_stock)
            logger.warning("[Validator] %s - insufficient stock: %s", participant, detail)
            raise ValidationError(
                f"[{participant}] " + _("Insufficient stock: %(detail)s") % {'detail': detail}
            )


