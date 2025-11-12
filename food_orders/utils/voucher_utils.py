# voucher_utils.py
from decimal import Decimal
import logging
from django.db import transaction
from django.core.exceptions import ValidationError
from ..models import AccountBalance, Voucher
from .balance_utils import calculate_base_balance

logger = logging.getLogger(__name__)

# ============================================================
# Account & Voucher Setup
# ============================================================



logger = logging.getLogger(__name__)

def setup_account_and_vouchers(participant, initial_vouchers=2, voucher_type="grocery") -> None:
    """
    Ensure a participant has an AccountBalance with calculated base balance
    and initial vouchers. Safe to call multiple times; will not overwrite existing accounts.
    """
    # --- Check if account already exists ---
    if hasattr(participant, "accountbalance"):
        logger.debug(f"Account already exists for participant {participant.id}")
        return

    # --- Calculate base balance ---
    base_balance = calculate_base_balance(participant)
    logger.debug(f"Calculated base balance {base_balance} for participant {participant.id}")

    # --- Create the account ---
    account = AccountBalance.objects.create(
        participant=participant,
        base_balance=base_balance
    )
    logger.debug(f"Created AccountBalance for participant {participant.id} with base_balance {base_balance}")

    # --- Create initial vouchers ---
    vouchers = [
        Voucher(account=account, voucher_type=voucher_type, active=True)
        for _ in range(initial_vouchers)
    ]
    Voucher.objects.bulk_create(vouchers)
    logger.debug(f"Created {len(vouchers)} {voucher_type} vouchers for participant {participant.id}")



# ============================================================
# Voucher Utility Functions
# ============================================================

def calculate_voucher_amount(voucher) -> Decimal:
    """
    Compute redeemable amount for a voucher.
    - Non-grocery vouchers return 0.
    - Consumed or expired vouchers return 0.
    - Apply multiplier if program is paused.
    """
    if voucher.voucher_type != "grocery":
        return Decimal("0.00")
    if voucher.state in ("consumed", "expired"):
        return Decimal("0.00")
    account = getattr(voucher, "account", None)
    if not account:
        return Decimal("0.00")

    base_balance = account.base_balance or Decimal("0.00")
    if getattr(voucher, "program_pause_flag", False):
        multiplier = Decimal(getattr(voucher, "multiplier", 1))
        return base_balance * multiplier
    return base_balance


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
    from ..models import OrderVoucher
    from ..tasks.logs import log_voucher_application_task

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

# ============================================================
# Voucher Application to Order
# ============================================================

def apply_vouchers_to_order(order, max_vouchers: int = 2) -> bool:
    """
    Apply eligible grocery vouchers to an order.
    Fully consumes vouchers even if order total is smaller than voucher value.
    Returns True if any voucher was applied.
    """
    from ..models import OrderValidationLog

    if order.status_type != "confirmed":
        raise ValidationError(f"Cannot apply vouchers to Order {order.id}, status={order.status_type}")

    account = order.account
    participant = account.participant
    remaining = order.total_price
    applied = False

    vouchers = get_active_vouchers(account, max_vouchers=max_vouchers)
    if not vouchers:
        logger.debug(f"[Voucher Apply] No eligible vouchers for Order {order.id}")
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
            order.save(update_fields=["paid"], skip_voucher=True)
            logger.debug(
                "[Voucher Apply] Applied vouchers to Order %s, remaining %.2f, paid: %s",
                order.id, remaining, order.paid
            )

    return applied
