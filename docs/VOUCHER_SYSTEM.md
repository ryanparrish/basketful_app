# Voucher System

> Last updated: January 2026

This document describes the voucher model and lifecycle.

## Overview

Vouchers are the primary mechanism for allocating shopping credits to participants. Each voucher has a monetary value and progresses through defined states.

## Voucher Model

**Location:** `apps/voucher/models.py::Voucher`

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `account` | ForeignKey | Link to participant's AccountBalance |
| `voucher_type` | CharField | `'grocery'` or `'life'` |
| `state` | CharField | Current lifecycle state |
| `active` | BooleanField | Whether voucher is active |
| `program_pause_flag` | BooleanField | Include during program pauses |
| `multiplier` | IntegerField | Balance multiplier (default: 1) |
| `voucher_amnt` | Property | Calculated voucher amount |

### Voucher Types

- **grocery** — Standard shopping voucher for food items
- **life** — Life skills program voucher

## Voucher States

```
pending → applied → consumed
                  ↘ expired
```

| State | Description |
|-------|-------------|
| `pending` | Voucher created but not yet applied to account |
| `applied` | Active voucher ready for use |
| `consumed` | Voucher fully used in completed order |
| `expired` | Voucher expired without being used |

## Voucher Settings

Global voucher configuration is managed via `VoucherSetting` (singleton pattern):

**Location:** `apps/voucher/models.py::VoucherSetting`

| Setting | Description |
|---------|-------------|
| `adult_amount` | Base amount per adult in household |
| `child_amount` | Base amount per child |
| `infant_modifier` | Additional amount per infant (diaper count) |
| `active` | Whether this setting is currently active |

Only one `VoucherSetting` can be active at a time.

## Voucher Consumption

When an order is completed, vouchers are consumed in order (oldest first) to cover the order total.

**Implementation:** `apps/orders/models.py::Order.confirm_order()`

## Bulk Voucher Creation

See [BULK_VOUCHER_CREATION.md](BULK_VOUCHER_CREATION.md) for batch voucher generation.

## Related Documentation

- [ACCOUNT_BALANCES.md](ACCOUNT_BALANCES.md) — How vouchers affect balances
- [BULK_VOUCHER_CREATION.md](BULK_VOUCHER_CREATION.md) — Batch creation
- [PROGRAM_PAUSES.md](PROGRAM_PAUSES.md) — Voucher behavior during pauses
