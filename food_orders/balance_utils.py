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


from decimal import Decimal
from django.utils.timezone import now

def calculate_available_balance(account_balance, limit: int = 2) -> Decimal:
    """
    Compute the available grocery voucher balance for an account.
    - Sums up to `limit` active grocery vouchers.
    - Each voucher's amount is multiplied by the applicable ProgramPause multiplier.
    """
    if not account_balance:
        return Decimal(0)

    # Lazy imports to avoid circular dependencies
    from .models import Voucher, ProgramPause

    # Get up to `limit` active grocery vouchers
    vouchers = account_balance.vouchers.filter(
        active=True,
        voucher_type="grocery"
    ).order_by("created_at")[:limit]

    total_balance = Decimal(0)
    today = now().date()

    # Get all active program pauses
    active_pauses = ProgramPause.objects.active()

    for voucher in vouchers:
        # Determine multiplier for this voucher
        multiplier = 1
        for pause in active_pauses:
            # Check if voucher creation date falls into the pause's relevant window
            days_until_start = (pause.start_date - voucher.created_at.date()).days
            duration = (pause.end_date - pause.start_date).days + 1

            if 11 <= days_until_start <= 14:
                if duration >= 14:
                    multiplier = max(multiplier, 3)  # extended pause
                elif duration >= 1:
                    multiplier = max(multiplier, 2)  # short pause

        total_balance += voucher.voucher_amnt * multiplier

    return total_balance

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
