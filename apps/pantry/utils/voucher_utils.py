# apps/pantry/utils/voucher_utils.py
"""Utility functions for managing vouchers and account balances."""
import logging
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.account.utils.balance_utils import calculate_base_balance
from apps.account.models import AccountBalance
from apps.voucher.models import Voucher, OrderVoucher
from apps.log.models import OrderValidationLog
from apps.log.tasks.logs import log_voucher_application_task

logger = logging.getLogger(__name__)

# ============================================================
# Account & Voucher Setup
# ============================================================


def setup_account_and_vouchers(
    participant, initial_vouchers=2, voucher_type="grocery"
) -> None:
    """
    Ensure a participant has an AccountBalance with calculated base balance
    and initial vouchers. Safe to call multiple times; will not overwrite 
    existing accounts.
    """
    # --- Check if account already exists ---
    if hasattr(participant, "accountbalance"):
        logger.debug(
            "Account already exists for participant %s", participant.id
        )
        return

    # --- Calculate base balance ---
    base_balance = calculate_base_balance(participant)
    logger.debug(
        "Calculated base balance %s for participant %s",
        base_balance, participant.id
    )

    # --- Create the account ---
    account = AccountBalance.objects.create(
        participant=participant,
        base_balance=base_balance
    )
    logger.debug(
        "Created AccountBalance for participant %s with base_balance %s",
        participant.id, base_balance
    )

    # --- Create initial vouchers ---
    vouchers = [
        Voucher(account=account, voucher_type=voucher_type, active=True)
        for _ in range(initial_vouchers)
    ]
    Voucher.objects.bulk_create(vouchers)
    logger.debug(
        "Created %d %s vouchers for participant %s",
        len(vouchers), voucher_type, participant.id
    )


# ============================================================
# Voucher Utility Functions
# ============================================================

def get_active_vouchers(account, voucher_type="grocery", max_vouchers=2):
    """
    Return a list of active vouchers for the given account, ordered by ID.
    """
    return list(
        account.vouchers.filter(
            voucher_type__iexact=voucher_type,
            state="applied",
            active=True
        ).order_by("id")[:max_vouchers]
    )


def consume_voucher(voucher, order, applied_amount):
    """
    Consume a voucher and create an OrderVoucher join record.
    """

    voucher.state = "consumed"
    voucher.notes = (voucher.notes or "") + f"Used on order {order.id} for ${applied_amount:.2f}; "
    voucher.save()

    OrderVoucher.objects.create(order=order, voucher=voucher, applied_amount=applied_amount)

    # Async logging
    log_voucher_application_task.delay(
        order_id=order.id,
        voucher_id=voucher.id,
        participant_id=getattr(order.account.participant, "id", None),
        applied_amount=applied_amount,
        remaining=None
    )

def apply_vouchers_to_order(order, max_vouchers: int = 2) -> bool:
    """
    Apply eligible grocery vouchers to an order.
    Fully consumes vouchers even if order total is smaller than voucher value.
    Returns True if any voucher was applied.
    """

    if order.status_type != "confirmed":
        raise ValidationError(f"Cannot apply vouchers to Order {order.id}, status={order.status_type}")

    account = order.account
    participant = account.participant
    remaining = order.total_price
    applied = False

    vouchers = get_active_vouchers(account, max_vouchers=max_vouchers)
    if not vouchers:
        logger.debug(
            "[Voucher Apply] No eligible vouchers for Order %s", order.id
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

            applied_amount = min(voucher.voucher_amnt, remaining)
            consume_voucher(voucher, order, applied_amount)
            remaining -= applied_amount
            applied = True

        # Update order paid status
        if applied:
            order.paid = remaining <= 0
            order.save(update_fields=["paid"])
            logger.debug(
                "[Voucher Apply] Applied vouchers to Order %s, remaining %.2f, paid: %s",
                order.id, remaining, order.paid
            )

    return applied
