# Account Balances

> Last updated: January 2026

This document describes the balance system used for participant accounts.

## Overview

Each participant has an `AccountBalance` that tracks multiple balance types derived from their applied vouchers.

## Balance Types

### Full Balance
Total value of all non-consumed grocery vouchers on the account.

**Calculation:** Sum of `voucher_amnt` for all vouchers where `state != 'consumed'` and `voucher_type = 'grocery'`

**Implementation:** `apps/account/utils/balance_utils.py::calculate_full_balance()`

### Available Balance
The amount a participant can spend on their current order. Limited to the sum of up to 2 oldest applied vouchers.

**Calculation:** 
```python
sum(voucher.voucher_amnt * voucher.multiplier 
    for voucher in oldest_N_applied_grocery_vouchers)
```

**Default limit:** 2 vouchers

**Special behavior:**
- During active ProgramPause periods with gate logic, only vouchers with `program_pause_flag=True` are included
- Respects voucher multipliers

**Implementation:** `apps/account/utils/balance_utils.py::calculate_available_balance()`

### Hygiene Balance
Reserved portion of available balance for hygiene products.

**Calculation:** `available_balance / 3`

**Implementation:** `apps/account/utils/balance_utils.py::calculate_hygiene_balance()`

### Go Fresh Balance
Fixed budget for fresh food items, based on household size.

**Calculation:** Determined by `GoFreshSettings` thresholds based on `adults + children` count

**Behavior:** 
- Resets with each order (doesn't accumulate)
- Independent of voucher amounts
- Can be disabled globally via `GoFreshSettings.is_enabled`

**Implementation:** `apps/account/models.py::AccountBalance.go_fresh_balance` property

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
