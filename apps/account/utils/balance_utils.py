from decimal import Decimal, ROUND_CEILING
from apps.voucher.models import VoucherSetting


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
      - Applies the CURRENT program-pause multiplier live (see
        _get_current_pause_multiplier) rather than each voucher's stored
        program_pause_flag/multiplier — those are only set by a one-shot
        batch job when a ProgramPause is saved, so a voucher created
        afterward (a new participant, a replenished voucher) would never
        get flagged and would silently stay un-doubled. Computing it live
        means it's always correct regardless of when the voucher was created.
    """
    if not account_balance:
        return Decimal(0)

    multiplier = Decimal(_get_current_pause_multiplier())

    vouchers = list(
        account_balance.vouchers.filter(
            state="applied",
            voucher_type="grocery"
        ).order_by("created_at")[:limit]
    )

    return sum(
        (getattr(v, "voucher_amnt", Decimal(0)) or Decimal(0)) * multiplier
        for v in vouchers
    )


def calculate_full_balance(account_balance) -> Decimal:
    """
    Compute the total balance for an account using all active grocery vouchers.
    Uses the Voucher model's `voucher_amnt` property.
    Includes pending, applied vouchers - excludes consumed and expired.
    """
    if not account_balance:
        return Decimal(0)
    
    vouchers = (
        account_balance.vouchers
        .filter(voucher_type="grocery")
        .exclude(state__in=['consumed', 'expired'])
        .order_by("created_at")
    )
    return sum(v.voucher_amnt for v in vouchers)


def calculate_hygiene_balance(account_balance) -> Decimal:
    """
    Compute the hygiene-specific balance for an account.
    Uses configurable ratio from HygieneSettings (default: 1/3 of available balance).
    """
    if not account_balance:
        return Decimal(0)

    # Import here to avoid circular dependency
    from apps.account.models import HygieneSettings
    
    settings = HygieneSettings.get_settings()
    if not settings.enabled:
        return Decimal(0)

    raw = account_balance.available_balance * settings.hygiene_ratio
    return raw.quantize(Decimal('1'), rounding=ROUND_CEILING)


def _get_current_pause_multiplier() -> int:
    """Return the active pause multiplier if we're in the ordering window, else 1."""
    from apps.lifeskills.models import ProgramPause
    pauses = ProgramPause.objects.all()  # default manager excludes archived
    multipliers = [pp.multiplier for pp in pauses]
    return max(multipliers, default=1)


def calculate_go_fresh_balance(account_balance) -> Decimal:
    """
    Calculate Go Fresh budget per order based on household size.
    
    This is a per-order budget that resets with each order submission.
    Unlike hygiene balance (which is a percentage of available balance),
    Go Fresh budget is fixed per order based on household size thresholds.
    
    Args:
        account_balance: AccountBalance instance
    
    Returns:
        Decimal: Go Fresh budget amount for this participant's household size
    
    Household Size Thresholds (default):
        - 1-2 people: $10.00
        - 3-5 people: $20.00
        - 6+ people: $25.00
    """
    if not account_balance:
        return Decimal(0)
    
    # Lazy import to avoid circular dependency
    from apps.account.models import GoFreshSettings
    
    # Get singleton settings
    settings = GoFreshSettings.get_settings()
    
    # Check if feature is enabled
    if not settings.enabled:
        return Decimal(0)
    
    # Get participant's household size
    try:
        household_size = account_balance.participant.household_size()
    except (AttributeError, TypeError):
        return Decimal(0)
    
    # Apply threshold logic
    if household_size <= settings.small_threshold:
        base = settings.small_household_budget
    elif household_size >= settings.large_threshold:
        base = settings.large_household_budget
    else:
        base = settings.medium_household_budget

    multiplier = _get_current_pause_multiplier()
    return base * Decimal(multiplier)
