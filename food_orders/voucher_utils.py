# voucher_utils.py
from decimal import Decimal
import logging
from django.db.models import Q
# voucher_utils.py
from django.db import transaction
from django.core.exceptions import ValidationError

# ============================================================
# Account + Voucher Setup
# ============================================================

def setup_account_and_vouchers(participant) -> None:
    """
    Ensure a participant has an account balance and initial grocery vouchers.
    """
    # Lazy import to avoid circular dependency
    from .models import AccountBalance, Voucher

    if hasattr(participant, "accountbalance"):
        return

    account = AccountBalance.objects.create(participant=participant)

    # Create 2 initial grocery vouchers
    Voucher.objects.bulk_create([
        Voucher(account=account, voucher_type="grocery", active=True)
        for _ in range(2)
    ])

# ============================================================
# Voucher Utilities
# ============================================================

from decimal import Decimal

def calculate_voucher_amount(voucher) -> Decimal:
    """
    Compute the redeemable amount for a voucher based on its account's base_balance.

    Rules:
        - Only grocery vouchers are assigned a balance.
        - If `voucher.program_pause_flag` is True, apply `voucher.multiplier`.
        - Otherwise, return the standard base_balance.
    """
    # Ignore non-grocery vouchers for now
    if voucher.voucher_type != "grocery":
        return Decimal("0.00")

    # Ignore vouchers that are spent
    if voucher.state in ("consumed", "expired"):
        return Decimal("0.00")

    account = voucher.account
    if not account:
        return Decimal("0.00")

    base_balance = account.base_balance or Decimal("0.00")

    # Apply voucher multiplier if program_pause_flag is True
    if getattr(voucher, "program_pause_flag", False):
        multiplier = Decimal(getattr(voucher, "multiplier", 1))
        return base_balance * multiplier

    # Standard base_balance if no multiplier
    return base_balance


from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)

def apply_vouchers_to_order(order, max_vouchers: int = 2) -> bool:
    """
    Apply eligible grocery vouchers to the given order using the OrderVoucher join table.
    - Only applies full vouchers (no partial usage)
    - Logs actions asynchronously via Celery task
    - Only applies vouchers if the order is confirmed
    Returns True if any voucher was applied, False otherwise.
    """
    from .models import OrderValidationLog, OrderVoucher
    from .tasks import log_voucher_application_task

    # --- Guard: only apply vouchers if order is confirmed ---
    if order.status_type != "confirmed":
        raise ValidationError(
            f"Cannot apply vouchers to Order {order.id} because it is not confirmed "
            f"(status={order.status_type})."
        )

    account = order.account
    participant = account.participant
    total_price = order.total_price
    remaining = total_price
    applied = False

    logger.debug(
        "[Voucher Apply] apply_vouchers_to_order() called for Order id=%s, participant=%s, status=%s",
        order.id,
        participant,
        order.status_type,
    )

    # Safety check: ensure account belongs to participant
    if account.participant != participant:
        raise ValueError(
            f"Account {account.id} does not belong to participant {participant.id} for order {order.id}"
        )

    # Fetch active grocery vouchers (only applied and active)
    vouchers = list(
        account.vouchers.filter(
            voucher_type__iexact="grocery",
            state="applied",
            active=True
        ).order_by("id")[:max_vouchers]
    )

    if not vouchers:
        logger.debug(
            "[Voucher Apply] No eligible vouchers found for Order id=%s, participant=%s",
            order.id,
            participant
        )
        OrderValidationLog.objects.create(
            participant=participant,
            message=f"No active grocery vouchers found for order {order.id}."
        )
        return False

    with transaction.atomic():
        for voucher in vouchers:
            if remaining <= 0:
                break

            # Only apply voucher if it fits entirely (no partial usage)
            if voucher.voucher_amnt <= remaining:
                applied_amount = voucher.voucher_amnt

                # Deactivate voucher
                voucher.state = "consumed"
                voucher.notes = (voucher.notes or "") + f"Fully used on order {order.id} for ${applied_amount:.2f}; "
                voucher.save()

                # Create join table record
                OrderVoucher.objects.create(
                    order=order,
                    voucher=voucher,
                    applied_amount=applied_amount
                )

                # Trigger async logging/task
                log_voucher_application_task.delay(
                    order_id=order.id,
                    voucher_id=voucher.id,
                    participant_id=participant.id,
                    applied_amount=applied_amount,
                    remaining=remaining - applied_amount
                )

                remaining -= applied_amount
                applied = True

        # Update order paid status if any vouchers were applied
        if applied:
            order.paid = remaining <= 0
            logger.debug(
                "[Voucher Apply] Applied %d voucher(s) to Order id=%s, remaining amount: %.2f, order paid: %s",
                len(vouchers),
                order.id,
                remaining,
                order.paid
            )
            order.save(update_fields=["paid"], skip_voucher=True)
        else:
            logger.debug(
                "[Voucher Apply] No vouchers were applied to Order id=%s (remaining: %.2f)",
                order.id,
                remaining
            )

    return applied
