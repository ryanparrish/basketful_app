from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING

from django.db.models import Prefetch

from apps.voucher.models import Voucher, VoucherSetting

# Balances reported for a participant who has no AccountBalance.
NO_ACCOUNT_BALANCES = {
    "full_balance": 0,
    "available_balance": 0,
    "hygiene_balance": 0,
    "go_fresh_balance": 0,
}

# Grocery vouchers that still count toward the full balance.
SPENT_VOUCHER_STATES = ('consumed', 'expired')

# Attribute an AccountBalance carries after open_grocery_vouchers_prefetch().
OPEN_GROCERY_VOUCHERS_ATTR = 'open_grocery_vouchers'


@dataclass(frozen=True)
class BalanceRules:
    """
    The global settings every balance depends on, loaded once.

    Listing many participants loads these once per request instead of once
    per balance per participant (#156).
    """
    pause_multiplier: int
    hygiene_settings: object
    go_fresh_settings: object

    @classmethod
    def load(cls) -> 'BalanceRules':
        from apps.account.models import GoFreshSettings, HygieneSettings
        return cls(
            pause_multiplier=_get_current_pause_multiplier(),
            hygiene_settings=HygieneSettings.get_settings(),
            go_fresh_settings=GoFreshSettings.get_settings(),
        )


def calculate_base_balance(participant) -> Decimal:
    """
    Calculate the base balance for a participant based on the active
    VoucherSetting.
    """
    if not participant:
        return Decimal(0)

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

    vouchers = account_balance.vouchers.filter(
        state="applied",
        voucher_type="grocery"
    ).order_by("created_at")[:limit]

    return available_from_vouchers(
        vouchers, _get_current_pause_multiplier(), limit=limit
    )


def calculate_full_balance(account_balance) -> Decimal:
    """
    Compute the total balance for an account using all active grocery vouchers.
    Uses the Voucher model's `voucher_amnt` property.
    Includes pending, applied vouchers - excludes consumed and expired.
    """
    if not account_balance:
        return Decimal(0)

    return full_from_vouchers(_open_grocery_vouchers_query(account_balance))


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
        return Decimal(0)  # skip computing the available balance
    return hygiene_from_available(account_balance.available_balance, settings)


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

    settings = GoFreshSettings.get_settings()
    if not settings.enabled:
        return Decimal(0)

    return go_fresh_for_participant(
        getattr(account_balance, 'participant', None),
        settings,
        _get_current_pause_multiplier(),
    )


# ── Pure balance rules ─────────────────────────────────────────────────────
# The functions below take everything they need as arguments, so a caller
# that has already loaded the vouchers and settings (the participant list)
# computes exactly what the per-account functions above compute.

def available_from_vouchers(open_grocery_vouchers, pause_multiplier, limit=2) -> Decimal:
    """Sum the oldest `limit` applied vouchers × the current pause multiplier."""
    multiplier = Decimal(pause_multiplier)
    applied = [v for v in open_grocery_vouchers if v.state == "applied"][:limit]
    return sum(
        (getattr(v, "voucher_amnt", Decimal(0)) or Decimal(0)) * multiplier
        for v in applied
    )


def full_from_vouchers(open_grocery_vouchers) -> Decimal:
    """Sum every grocery voucher that is not consumed or expired."""
    return sum(v.voucher_amnt for v in open_grocery_vouchers)


def hygiene_from_available(available_balance, hygiene_settings) -> Decimal:
    """The hygiene share of the available balance, rounded up to whole dollars."""
    if not hygiene_settings.enabled:
        return Decimal(0)
    raw = available_balance * hygiene_settings.hygiene_ratio
    return raw.quantize(Decimal('1'), rounding=ROUND_CEILING)


def go_fresh_for_participant(participant, go_fresh_settings, pause_multiplier) -> Decimal:
    """The per-order Go Fresh budget for the participant's household size."""
    if not go_fresh_settings.enabled:
        return Decimal(0)

    try:
        household_size = participant.household_size()
    except (AttributeError, TypeError):
        return Decimal(0)

    if household_size <= go_fresh_settings.small_threshold:
        base = go_fresh_settings.small_household_budget
    elif household_size >= go_fresh_settings.large_threshold:
        base = go_fresh_settings.large_household_budget
    else:
        base = go_fresh_settings.medium_household_budget

    return base * Decimal(pause_multiplier)


# ── Balances for many accounts at once ─────────────────────────────────────

def open_grocery_vouchers_prefetch(lookup_prefix='') -> Prefetch:
    """
    Prefetch each account's open grocery vouchers in one query.

    `lookup_prefix` is the path to the AccountBalance, e.g. 'accountbalance__'
    when prefetching from a Participant queryset.
    """
    return Prefetch(
        f'{lookup_prefix}vouchers',
        queryset=(
            Voucher.objects
            .filter(voucher_type="grocery")
            .exclude(state__in=SPENT_VOUCHER_STATES)
            .order_by("created_at")
        ),
        to_attr=OPEN_GROCERY_VOUCHERS_ATTR,
    )


def summarize_balances(account_balance, rules: BalanceRules) -> dict:
    """
    All four balances for one account, from preloaded vouchers when present.

    Matches Participant.balances(), which computes each balance with its own
    queries.
    """
    open_grocery_vouchers = getattr(account_balance, OPEN_GROCERY_VOUCHERS_ATTR, None)
    if open_grocery_vouchers is None:
        open_grocery_vouchers = list(_open_grocery_vouchers_query(account_balance))

    available_balance = available_from_vouchers(
        open_grocery_vouchers, rules.pause_multiplier
    )
    return {
        "full_balance": full_from_vouchers(open_grocery_vouchers),
        "available_balance": available_balance,
        "hygiene_balance": hygiene_from_available(
            available_balance, rules.hygiene_settings
        ),
        "go_fresh_balance": go_fresh_for_participant(
            getattr(account_balance, 'participant', None),
            rules.go_fresh_settings,
            rules.pause_multiplier,
        ),
    }


def _open_grocery_vouchers_query(account_balance):
    return (
        account_balance.vouchers
        .filter(voucher_type="grocery")
        .exclude(state__in=SPENT_VOUCHER_STATES)
        .order_by("created_at")
    )
