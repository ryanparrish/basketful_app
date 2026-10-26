# Account Balances

> Last updated: 2026-10-25

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
sum(voucher.voucher_amnt * voucher.multiplier 
    for voucher in oldest_N_applied_grocery_vouchers)
```

**Default limit:** 2 vouchers

**Special behavior:**
- During active ProgramPause periods with gate logic, only vouchers with `program_pause_flag=True` are included
- Respects voucher multipliers

**Implementation:** `apps/account/utils/balance_utils.py::calculate_available_balance()`

### Hygiene Balance
A cap on how much of the available balance hygiene items may use. It is a cap, not a reservation: hygiene items are paid from the available balance, and food can use all of it when the cart has no hygiene items.

**Calculation:** `available_balance * hygiene_ratio`, rounded **up** to the nearest whole dollar (`ROUND_CEILING`)

**Configurable via `HygieneSettings`** (singleton model, admin-editable):
- `hygiene_ratio` — default `1/3` (0.3333...), stored as a high-precision decimal
- `enabled` — if `False`, hygiene balance is always `0`

**Implementation:** `apps/account/utils/balance_utils.py::calculate_hygiene_balance()`

### Go Fresh Balance
A cap on how much of the available balance Go Fresh items may use, set by household size. Like hygiene, Go Fresh items are paid from the available balance; this is not extra money.

**Calculation:** Determined by `GoFreshSettings` thresholds based on `adults + children` count

**Behavior:** 
- Resets with each order (doesn't accumulate) — it's a computed property, not a stored running balance
- Independent of voucher amounts
- Can be disabled globally via `GoFreshSettings.enabled`
- Multiplied by the active `ProgramPause` multiplier, if any (see `apps/lifeskills/models.py::ProgramPause.multiplier` — 2x for short pauses, 3x for extended pauses, 1x otherwise). This is the same pause-driven multiplier concept used for grocery vouchers.

**Implementation:** `apps/account/models.py::AccountBalance.go_fresh_balance` property, backed by `apps/account/utils/balance_utils.py::calculate_go_fresh_balance()`

See [GO_FRESH_BUDGET_FEATURE.md](GO_FRESH_BUDGET_FEATURE.md) for detailed Go Fresh implementation.

## How an Order Is Checked Against the Balances

The vouchers behind the available balance pay for the whole order: `Order._consume_vouchers()` charges the order total, hygiene and Go Fresh items included. So every order must pass three checks:

1. **Whole cart ≤ available balance**
2. **Hygiene items ≤ hygiene balance**
3. **Go Fresh items ≤ Go Fresh balance** (only while Go Fresh is enabled)

All three follow `ProgramSettings` grace the same way. With grace enabled, going over by no more than `grace_amount` is a warning: the participant sees `grace_message`, the order goes through, and a `GraceAllowanceLog` entry is written. Any larger overage, or any overage at all with grace disabled, blocks the order.

Example: available $100, hygiene $34, Go Fresh $10. $60 food + $30 hygiene + $8 Go Fresh passes. $95 food + $8 Go Fresh is over the available balance by $3. $40 food + $40 hygiene is over the hygiene balance by $6.

The rule lives in one place, `apps/orders/utils/balance_rules.py::check_cart_balances()`, used by the participant's live cart check (`validate-cart`), order creation (`OrderValidation.validate_order_items()`) and `Order.clean()`, so they always agree. Which check a product falls under comes from `Product.budget` (the protected "Hygiene" and "Go Fresh" category names). The participant app shows the same rule in `useBudgets`: the food line counts the whole cart, and the hygiene and Go Fresh lines never show more than is left overall.

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
