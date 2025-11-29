from decimal import Decimal
from django.utils import timezone
from apps.voucher.models import VoucherSetting
from apps.lifeskills.models import ProgramPause


def calculate_base_balance(participant) -> Decimal:
    """
    Calculate the base balance for a participant based on the active 
    VoucherSetting.
    """
    if not participant:
        return Decimal(0)

    # Lazy import to avoid circular dependency

    setting = VoucherSetting.objects.filter(active=True).first()
    if not setting:
        return Decimal(0)

    adults = getattr(participant, "adults", 0)
    children = getattr(participant, "children", 0)
    diaper_count = getattr(participant, "diaper_count", 0)

    return (
        Decimal(adults) * Decimal(setting.adult_amount) +
        Decimal(children) * Decimal(setting.child_amount) +
        Decimal(diaper_count) * Decimal(setting.infant_modifier)
    )


def calculate_available_balance(account_balance, limit=2):
    """
    Compute the available grocery voucher balance for an account.

    Rules:
      - Sums up to `limit` active grocery vouchers.
      - Uses each voucher's multiplier.
      - If a ProgramPause is currently active, only include vouchers 
        with program_pause_flag=True.
    """
    if not account_balance:
        return Decimal(0)

    now = timezone.now()

    # Global active ProgramPauses
    active_pauses = ProgramPause.objects.filter(
        pause_start__lte=now,
        pause_end__gte=now
    )

    # Dynamic gate check
    gate_active = any(getattr(pp, "is_active_gate", False) for pp in active_pauses)

    # Base queryset: active grocery vouchers
    vouchers_qs = account_balance.vouchers.filter(
        state="applied",
        voucher_type="grocery"
    ).order_by("created_at")

    # Convert to list for Python-level filtering
    vouchers = list(vouchers_qs)

    # Only include vouchers flagged for pause if gate is active
    if gate_active:
        vouchers = [v for v in vouchers if getattr(v, "program_pause_flag", False)]

    # Apply limit **after filtering**
    vouchers = vouchers[:limit]

    # Compute total balance using voucher amount * multiplier
    total_balance = sum(
        (getattr(v, "voucher_amnt", Decimal(0)) or Decimal(0)) *
        (getattr(v, "multiplier", Decimal(1)) or Decimal(1))
        for v in vouchers
    )

    return total_balance


def calculate_full_balance(account_balance) -> Decimal:
    """
    Compute the total balance for an account using all active grocery vouchers.
    Uses the Voucher model's `voucher_amnt` property.
    """
    if not account_balance:
        return Decimal(0)
    
    vouchers = (
        account_balance.vouchers
        .filter(state__isnull=True, voucher_type="grocery")  
        .exclude(state='consumed')                             
        .order_by("created_at")
    )
    return sum(v.voucher_amnt for v in vouchers)


def calculate_hygiene_balance(account_balance) -> Decimal:
    """
    Compute the hygiene-specific balance for an account.
    Defined as 1/3 of the full balance.
    """
    if not account_balance:
        return Decimal(0)

    return account_balance.available_balance / Decimal(3)
