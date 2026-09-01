# Voucher System

> Last updated: 2026-07-13

This document describes the voucher model and lifecycle.

## Overview

Vouchers are the primary mechanism for allocating shopping credits to participants. Each voucher has a monetary value and progresses through defined states.

## Voucher Model

**Location:** `apps/voucher/models.py::Voucher`

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `account` | ForeignKey | Link to participant's `AccountBalance` (`related_name='vouchers'`) |
| `voucher_type` | CharField | `'grocery'` or `'life'` (default `'grocery'`) |
| `state` | CharField | Current lifecycle state (not directly editable — see below) |
| `active` | BooleanField | Whether the voucher counts toward available balance (default `True`) |
| `program_pause_flag` | BooleanField | Set when the voucher's activation/deactivation was driven by a program pause |
| `multiplier` | IntegerField | Balance multiplier applied during program pauses (default: 1; not directly editable). See `PROGRAM_PAUSES.md`. |
| `notes` | TextField | Free-text notes; used to record bulk-creation source and order-consumption history |
| `created_at` / `updated_at` | DateTimeField | Auto-managed timestamps |
| `voucher_amnt` | Property | Redeemable amount — see below |

`voucher_amnt` is computed by `apps/voucher/utils.py::calculate_voucher_amount()`:
- Non-`grocery` vouchers always return `$0.00`.
- `consumed` or `expired` vouchers always return `$0.00`.
- Otherwise it returns the account's `base_balance` (the pause `multiplier` is **not** applied here — it's applied separately wherever the effective amount matters, e.g. order consumption and the frontend "Effective Amount" display).

`Voucher.objects` is the default manager; `Voucher.active_vouchers` (`ActiveVouchersManager`) returns only vouchers with `active=True`.

### Voucher Types

- **grocery** — Standard shopping voucher for food items
- **life** — Life skills program voucher

## Voucher States

```
pending ──apply──> applied ──(order confirmed)──> consumed
   │                  │                               │
   └──expire──> expired <──expire──────────────────────┘
                                (order cancelled restores
                                 consumed → applied)
```

| State | Description |
|-------|-------------|
| `pending` | Voucher created but not yet applied to the account |
| `applied` | Active voucher available to cover orders |
| `consumed` | Voucher used (partially or fully) by a confirmed order |
| `expired` | Voucher expired without being used; terminal state |

`consumed` and `expired` are terminal for direct admin/API transitions — the model's `clean()` method (`apps/voucher/models.py::Voucher.clean()`) raises a `ValidationError` if an existing voucher's state changes away from `consumed`, and also rejects any voucher that is both `active=True` and `state='consumed'`. There is no equivalent model-level guard for `expired`; that transition is enforced in the API/admin layer instead (see below). The one exception to "consumed is terminal" is order cancellation, which uses `.update()` to bypass these restrictions and restore consumed vouchers to `applied` (see Voucher Consumption below).

### How state changes happen

There is no automatic expiration job. State changes come from three places:

1. **Order confirmation** — `applied` → `consumed`, automatic (see Voucher Consumption below).
2. **Voucher API** (`apps/voucher/api/views.py::VoucherViewSet`), used by the React admin frontend:
   - `POST /api/vouchers/{id}/apply/` — `pending` → `applied`.
   - `POST /api/vouchers/{id}/revert_to_pending/` — `applied` → `pending`.
   - `POST /api/vouchers/{id}/expire/` — `pending` or `applied` → `expired` (also sets `active=False`); rejects `consumed` vouchers and already-`expired` ones.
   - `POST /api/vouchers/bulk_update_status/` — bulk version of the above; allowed transitions are `pending → {applied, expired}` and `applied → {expired}` (bulk does **not** support `applied → pending`, only the single-voucher `revert_to_pending` action does).
3. **Django Admin action** — `mark_as_applied` (`apps/voucher/admin.py`) is a changelist action that force-sets `state='applied'` via `queryset.update()` for selected vouchers, bypassing `clean()`.

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

There is no `confirm_order()` method. Vouchers are consumed as a side effect of `Order.save()`: when an order's `status` transitions to `"confirmed"`, `save()` calls `self._consume_vouchers()` followed by `self._decrement_stock()`, all inside one `transaction.atomic()` block.

**Implementation:** `apps/orders/models.py::Order._consume_vouchers()`

Business rule (grocery vouchers only — `life` vouchers are never consumed by orders):

- Up to **2** active, `applied` grocery vouchers for the account are selected (`select_for_update()`, ordered oldest-first by `created_at`). A single order can never consume more than 2 vouchers, regardless of order size.
- If the order total fits within one voucher's effective amount, only **one** voucher is consumed; otherwise **both** available vouchers are consumed.
- If the order total exceeds the combined effective balance of those (at most 2) vouchers, `_consume_vouchers()` raises a `ValidationError` — unless the confirming request set:
  - `_bypass_balance_check=True` (requires `_bypass_user`, a staff member with the `can_bypass_order_transitions` permission) — consumes what's available anyway and logs a `WARNING` to `OrderValidationLog`, or
  - `_charitable_bypass=True` (requires `_bypass_user`) — waives voucher consumption entirely (order is given as a gift); stock is still decremented.
- Each consumed voucher is updated to `active=False, state='consumed'` (via `.update()`, bypassing the model's `editable=False`/`clean()` restrictions) and an `OrderVoucher` row is created recording the `applied_amount`.
- "Effective amount" = `voucher.voucher_amnt * voucher.multiplier` — this is where the program-pause multiplier actually gets applied to consumption math.

Cancelling a confirmed order reverses this: `Order._restore_on_cancel()` restores each `OrderVoucher`-linked voucher from `consumed` back to `applied` (and deletes the `OrderVoucher` rows), and additively restores decremented product stock.

### OrderVoucher

`apps/voucher/models.py::OrderVoucher` is the join model tracking which vouchers paid for which order:

| Field | Type | Description |
|-------|------|-------------|
| `order` | ForeignKey | `orders.Order`, `related_name='applied_vouchers'` |
| `voucher` | ForeignKey | `Voucher`, `related_name='order_applications'` |
| `applied_amount` | DecimalField | Amount of this voucher applied to the order |
| `applied_at` | DateTimeField | Auto-set on creation |

It's read-only via the API (`OrderVoucherViewSet` in `apps/voucher/api/views.py`) and powers the voucher redemption report (`apps/voucher/views_reports.py`, Django Admin → Vouchers → "📊 Redemption Report").

## Voucher API

`apps/voucher/api/` exposes `VoucherViewSet`, `VoucherSettingViewSet`, and `OrderVoucherViewSet` (registered under `/api/vouchers/`, `/api/voucher-settings/`, `/api/order-vouchers/`). Beyond standard CRUD, notable custom actions on `VoucherViewSet` include `active_vouchers`, `by_program`, `bulk_create`, `bulk_create/preview`, `bulk_update_status`, `apply`, `revert_to_pending`, and `expire` — see Voucher States above and [BULK_VOUCHER_CREATION.md](BULK_VOUCHER_CREATION.md) for how these are used.

## Bulk Voucher Creation

See [BULK_VOUCHER_CREATION.md](BULK_VOUCHER_CREATION.md) for batch voucher generation. There are now two independent bulk-creation paths: a React admin frontend page (the one linked from the voucher list's "Create Vouchers" button) backed by the API, and a legacy Django Admin multi-step view.

## Related Documentation

- [ACCOUNT_BALANCES.md](ACCOUNT_BALANCES.md) — How vouchers affect balances
- [BULK_VOUCHER_CREATION.md](BULK_VOUCHER_CREATION.md) — Batch creation
- [PROGRAM_PAUSES.md](PROGRAM_PAUSES.md) — Voucher behavior during pauses
