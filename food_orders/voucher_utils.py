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
