from decimal import Decimal


def calculate_base_balance(participant) -> Decimal:
    """
    Calculate the base balance for a participant based on the active VoucherSetting.
    """
    if not participant:
        return Decimal(0)

    # Lazy import to avoid circular dependency
    from .models import VoucherSetting

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


def calculate_available_balance(account_balance, limit: int = 2) -> Decimal:
    """
    Compute the available voucher balance for an account.
    - Sums up to `limit` active grocery vouchers.
    - Uses the Voucher model's `voucher_amnt` property.
    """
    if not account_balance:
        return Decimal(0)

    # Lazy import to avoid circular dependency
    from .models import Voucher

    vouchers = account_balance.vouchers.filter(
        active=True,
        voucher_type="grocery"
    ).order_by("created_at")[:limit]

    return sum(v.voucher_amnt for v in vouchers)


def calculate_full_balance(account_balance) -> Decimal:
    """
    Compute the total balance for an account using all active grocery vouchers.
    Uses the Voucher model's `voucher_amnt` property.
    """
    if not account_balance:
        return Decimal(0)

    from .models import Voucher

    vouchers = account_balance.vouchers.filter(
        active=True,
        voucher_type="grocery"
    ).order_by("created_at")

    return sum(v.voucher_amnt for v in vouchers)


def calculate_hygiene_balance(account_balance) -> Decimal:
    """
    Compute the hygiene-specific balance for an account.
    Defined as 1/3 of the full balance.
    """
    if not account_balance:
        return Decimal(0)

    return account_balance.full_balance / Decimal(3)
