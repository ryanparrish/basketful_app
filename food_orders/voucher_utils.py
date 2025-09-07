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
        - Only the first `limit` active vouchers receive any active ProgramPause multiplier.
        - Subsequent vouchers receive the standard base_balance.
    """
    # Lazy import to avoid circular dependency
    from .models import ProgramPause

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
        # Only one ProgramPause exists, filtered by availability window
        active_pause = ProgramPause.objects.with_annotations().filter(is_active_gate=True).first()
        multiplier = Decimal(active_pause.multiplier) if active_pause else Decimal(1)
        return base_balance * multiplier

    # Standard base_balance for vouchers beyond the first `limit`
    return base_balance
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

def apply_vouchers(order, max_vouchers: int = 2) -> bool:
    """
    Apply eligible grocery vouchers to the given order according to business rules:
      - No partial usage of vouchers.
      - If order total <= first voucher, mark the first voucher inactive.
      - If order total >= sum of first two active vouchers, mark both first two inactive.
      - If order total > first voucher and < sum of first two vouchers, mark both first two inactive.
    Returns True if any voucher was marked inactive (i.e., applied).
    """
    # Get first `max_vouchers` active grocery vouchers for this account
    vouchers = list(
        order.account.vouchers.filter(voucher_type__iexact="grocery", active=True)
        .order_by("id")[:max_vouchers]
    )

    if not vouchers:
        return False  # No vouchers available

    applied = False
    total_price = order.total_price

    if len(vouchers) == 1:
        # Only one voucher available
        if total_price <= vouchers[0].voucher_amnt:
            vouchers[0].active = False
            vouchers[0].save(update_fields=["active"])
            applied = True
    elif len(vouchers) >= 2:
        first, second = vouchers[0], vouchers[1]
        first_amount = first.voucher_amnt
        second_amount = second.voucher_amnt
        combined = first_amount + second_amount

        if total_price <= first_amount:
            first.active = False
            first.save(update_fields=["active"])
            applied = True
        elif total_price >= combined:
            first.active = False
            second.active = False
            first.save(update_fields=["active"])
            second.save(update_fields=["active"])
            applied = True
        elif first_amount < total_price < combined:
            first.active = False
            second.active = False
            first.save(update_fields=["active"])
            second.save(update_fields=["active"])
            applied = True

    if applied:
        order.paid = True
        # Avoid recursion if `save` triggers voucher logic
        order.save(update_fields=["paid"], skip_voucher=True)

    return applied
