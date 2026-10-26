# food_orders.utils.order_validation.py
"""Utilities for validating orders and order items."""
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from typing import List, Any
from dataclasses import dataclass
import logging
from .balance_rules import BalanceViolation, check_cart_balances
from apps.pantry.models import CategoryLimitValidator
from core.models import ProgramSettings

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
    def enforce_balances(items, participant, account_balance) -> List[BalanceViolation]:
        """
        Raise if the items go over a balance beyond the grace allowance;
        otherwise return the overages grace allowed.
        """
        violations = check_cart_balances(items, account_balance, ProgramSettings.get_settings())
        blocking = [v for v in violations if v.is_blocking]
        if blocking:
            logger.warning(
                "[Validator] %s - over balance: %s",
                participant,
                "; ".join(f"{v.balance} ${v.total:.2f} > ${v.limit:.2f}" for v in blocking),
            )
            raise ValidationError([v.message for v in blocking])
        return violations

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
        2. Food, hygiene and Go Fresh balances
        3. Stock

        Returns the balance overages the grace allowance let through, so
        the caller can record them against the order it creates.
        """
        if not participant:
            logger.debug("[Validator] No participant found — skipping validation.")
            return []

        logger.debug("[Validator] Validating for Participant: %s", participant)

        # Step 0: Block ordering entirely while a program pause is in progress
        OrderValidation.enforce_program_pause(participant)

        # Step 1: Validate category-level limits using CategoryLimitValidator
        CategoryLimitValidator.validate_category_limits(items, participant)

        # Step 2: Food, hygiene and Go Fresh balances, the same rule the
        # cart applies (apps/orders/utils/balance_rules.py)
        grace_violations = OrderValidation.enforce_balances(items, participant, account_balance)

        # Step 3: Validate stock availability — prevent confirming orders for out-of-stock items.
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

        return grace_violations


