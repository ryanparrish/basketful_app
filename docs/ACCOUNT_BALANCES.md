# Account Balances

> Last updated: 2026-10-17

This document describes the balance system used for participant accounts.

## Overview

Each participant has an `AccountBalance` that tracks multiple balance types derived from their applied vouchers.

## Balance Types

### Full Balance
Total value of all non-consumed, non-expired grocery vouchers on the account.

**Calculation:** Sum of `voucher_amnt` for all vouchers where `voucher_type = 'grocery'` and `state` is not `'consumed'` or `'expired'`

**Implementation:** `apps/account/utils/balance_utils.py::calculate_full_balance()`

### Available Balance
The amount a participant can spend on their current order. Limited to the sum of up to 2 oldest applied vouchers.

**Calculation:** 
```python
multiplier = _get_current_pause_multiplier()   # live: 2 or 3 in a double/triple week, else 1
sum(voucher.voucher_amnt * multiplier
    for voucher in oldest_N_applied_grocery_vouchers)
```

**Default limit:** 2 vouchers

**Special behavior:**
- Applies the **live** program-pause multiplier, not each voucher's stored `multiplier`/`program_pause_flag` (those are set by a one-off job when a pause is saved, so vouchers created afterwards would miss them). No voucher is excluded during a pause.
- An order may exceed it only by the global grace allowance (Settings → Grace, off by default); see [VOUCHER_SYSTEM.md](VOUCHER_SYSTEM.md#voucher-consumption).
- At confirmation, vouchers are consumed using the multiplier recorded on the order when it was placed (`pause_multiplier_at_creation`), not the live one.

**Implementation:** `apps/account/utils/balance_utils.py::calculate_available_balance()`

### Hygiene Balance
Reserved portion of available balance for hygiene products.

**Calculation:** `available_balance * hygiene_ratio`, rounded **up** to the nearest whole dollar (`ROUND_CEILING`)

**Configurable via `HygieneSettings`** (singleton model, admin-editable):
- `hygiene_ratio` — default `1/3` (0.3333...), stored as a high-precision decimal
- `enabled` — if `False`, hygiene balance is always `0`

**Implementation:** `apps/account/utils/balance_utils.py::calculate_hygiene_balance()`

### Go Fresh Balance
Fixed budget for fresh food items, based on household size.

**Calculation:** Determined by `GoFreshSettings` thresholds based on `adults + children` count

**Behavior:** 
- Resets with each order (doesn't accumulate) — it's a computed property, not a stored running balance
- Independent of voucher amounts
- Can be disabled globally via `GoFreshSettings.enabled`
- Multiplied by the active `ProgramPause` multiplier, if any (see `apps/lifeskills/models.py::ProgramPause.multiplier` — 2x for short pauses, 3x for extended pauses, 1x otherwise). This is the same pause-driven multiplier concept used for grocery vouchers.

**Implementation:** `apps/account/models.py::AccountBalance.go_fresh_balance` property, backed by `apps/account/utils/balance_utils.py::calculate_go_fresh_balance()`

See [GO_FRESH_BUDGET_FEATURE.md](GO_FRESH_BUDGET_FEATURE.md) for detailed Go Fresh implementation.

## Base Balance

The theoretical balance for a household based on active `VoucherSetting` configuration:

```python
base_balance = (adults * adult_amount) + (children * child_amount) + (diaper_count * infant_modifier)
```

**Implementation:** `apps/account/utils/balance_utils.py::calculate_base_balance()`

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — System overview
- [VOUCHER_SYSTEM.md](VOUCHER_SYSTEM.md) — Voucher lifecycle
- [GO_FRESH_BUDGET_FEATURE.md](GO_FRESH_BUDGET_FEATURE.md) — Go Fresh details
- [PROGRAM_PAUSES.md](PROGRAM_PAUSES.md) — Program pause effects on balances
