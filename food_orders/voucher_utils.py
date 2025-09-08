from decimal import Decimal
from django.db.models import Count
from decimal import Decimal

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
from django.db.models import Count
from django.utils.timezone import now

def calculate_voucher_amount(voucher, limit: int = 2) -> Decimal:
    """
    Compute the redeemable amount for a voucher based on its account's base_balance.

    Rules:
        - Only grocery vouchers are assigned a balance.
        - Only the first `limit` active vouchers receive any active ProgramPause multiplier.
        - Subsequent vouchers receive the standard base_balance.
    """
    from .models import ProgramPause

    # Only grocery vouchers have a balance
    if getattr(voucher, "voucher_type", None) != "grocery":
        return Decimal(0)

    account = getattr(voucher, "account", None)
    if not account or account.base_balance is None:
        return Decimal(0)

    base_balance = account.base_balance

    # Count the number of active vouchers created before this one
    redeemed_count = (
        account.vouchers.filter(active=True, created_at__lt=voucher.created_at)
        .aggregate(count=Count('id'))['count']
    )

    # Apply ProgramPause multiplier only if within the first `limit` vouchers
    if redeemed_count < limit:
        active_pause = ProgramPause.objects.with_annotations().filter(is_active_gate=True).first()
        multiplier = Decimal(active_pause.multiplier) if active_pause else Decimal(1)
        return base_balance * multiplier

    # Standard base_balance for vouchers beyond the first `limit`
    return base_balance

import logging


logger = logging.getLogger(__name__)

def apply_vouchers(order, max_vouchers: int = 2) -> bool:
    """
    Apply eligible grocery vouchers to the given order using voucher.voucher_amnt().
    Handles:
      - total_price <= first voucher amount (single voucher applied)
      - total_price == first voucher amount (exact match)
      - total_price > first voucher amount (multi-voucher application)
    Safety check: ensures the account belongs to the correct participant.
    Logs actions to VoucherLog, or OrderValidationLog if no vouchers exist.
    Returns True if any voucher was applied.
    """
    # Lazy imports to avoid circular dependencies
    from .models import VoucherLog, OrderValidationLog

    account = order.account
    participant = account.participant  # access participant via account

    # Safety check
    if account.participant != participant:
        raise ValueError(
            f"Account {account.id} does not belong to participant {participant.id} for order {order.id}"
        )

    total_price = order.total_price  # Decimal
    applied = False

    # Fetch up to max_vouchers active grocery vouchers
    vouchers = list(
        account.vouchers.filter(voucher_type__iexact="grocery", active=True)
        .order_by("id")[:max_vouchers]
    )

    if not vouchers:
        # No vouchers: log to OrderValidationLog
        OrderValidationLog.objects.create(
            participant=participant,
            message=f"No active grocery vouchers found for order {order.id}.",
        )
        return False

    first_voucher = vouchers[0]
    first_amount = first_voucher.voucher_amnt

    # --- Handle total_price <= first voucher ---
    if total_price <= first_amount:
        first_voucher.active = False
        note_type = "Fully" if total_price == first_amount else "Partially"
        first_voucher.notes = (first_voucher.notes or "") + f"{note_type} used on order {order.id} for ${total_price:.2f}; "
        first_voucher.save()
        applied = True

        VoucherLog.objects.create(
            order=order,
            voucher=first_voucher,
            participant=participant,
            message=f"{note_type} used voucher {first_voucher.id} for ${total_price:.2f}.",
            log_type=VoucherLog.INFO,
        )

        order.paid = True
        order.save(update_fields=["paid"], skip_voucher=True)
        return True

    # --- Multi-voucher application ---
    amount_needed = total_price
    for voucher in vouchers:
        if amount_needed <= 0:
            break

        voucher_amount = voucher.voucher_amnt
        applied_amount = min(amount_needed, voucher_amount)
        if applied_amount <= 0:
            continue

        voucher.active = False
        note_type = "Fully" if applied_amount == voucher_amount else "Partially"
        voucher.notes = (voucher.notes or "") + f"{note_type} used on order {order.id} for ${applied_amount:.2f}; "
        voucher.save()

        amount_needed -= applied_amount
        applied = True

        VoucherLog.objects.create(
            order=order,
            voucher=voucher,
            participant=participant,
            message=f"{note_type} used voucher {voucher.id} for ${applied_amount:.2f}, "
                    f"remaining amount needed: ${amount_needed:.2f}",
            log_type=VoucherLog.INFO,
        )

    if applied:
        order.paid = True
        order.save(update_fields=["paid"], skip_voucher=True)

    return applied
