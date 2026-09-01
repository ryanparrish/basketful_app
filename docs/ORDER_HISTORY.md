# Order History & Validation Logs

> Last updated: 2026-07-13

This document describes order tracking and validation logging.

## Overview

The system maintains detailed records of orders and their validation history for auditing and debugging.

## Order Model

**Location:** `apps/orders/models.py::Order`

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `user` | ForeignKey (nullable) | `auth.User` who placed the order (`SET_NULL` on delete) |
| `account` | ForeignKey | `account.AccountBalance` the order draws from (`PROTECT` on delete) |
| `order_number` | CharField | Unique generated identifier, e.g. `ORD-20260713-A1B2C3` (`Order._generate_order_number`) |
| `status` | CharField | Order status — see below |
| `paid` | BooleanField | Set `True` when vouchers are consumed at confirmation |
| `go_fresh_total` | DecimalField | Go Fresh subtotal, calculated and persisted in `Order.confirm()` |
| `program_pause_at_creation` / `pause_multiplier_at_creation` | CharField / IntegerField (nullable) | Snapshot of an active program pause at the time the order was created, for audit |
| `success_viewed` | BooleanField | Whether the participant has seen the order-success page |
| `order_date` | DateTimeField | Set on creation (`auto_now_add`) |
| `created_at` / `updated_at` | DateTimeField | Standard timestamps |

There is **no** persisted `total`, `hygiene_total`, or `confirmed_at` field. The grand total is computed on demand by `Order.total_price()` (sums `OrderItem.total_price()`), and the food / hygiene / Go Fresh split is computed on the fly — in `Order.clean()` and in the `validate-cart` API action — by checking each item's `product.category.name`. "When was it confirmed" is answered by `updated_at` on the row where `status == "confirmed"`, not a dedicated timestamp.

### Order Statuses

| Status | Description |
|--------|-------------|
| `pending` | Order submitted, awaiting confirmation. A participant may only have one `pending`/`confirmed`/`packing` order at a time (`Order.clean()` duplicate-active-order guard). |
| `confirmed` | Order confirmed — vouchers consumed, stock decremented (`Order.confirm()` / `_consume_vouchers()` / `_decrement_stock()`). |
| `packing` | Order handed off for warehouse packing (part of the combined-order/packing-list workflow). |
| `completed` | Order fulfilled. |
| `cancelled` | Order cancelled. If it had been confirmed, `Order._restore_on_cancel()` returns consumed vouchers to `applied` and adds stock back. |

Staff with the `orders.can_bypass_order_transitions` permission can move an order between any of the active statuses out of the normal forward-only flow (see `OrderViewSet.bulk_update_status` / `.confirm` in `apps/orders/api/views.py`).

## Order Items

**Location:** `apps/orders/models.py::OrderItem`

Fields: `order`, `product`, `quantity`, `price`, `price_at_order`, `created_at`.

`price_at_order` is set once, the first time the item is saved, and never changes — a true snapshot. `price`, however, is **overwritten to the product's current price on every save** (`OrderItem.save()`), and `total_price()` (`quantity * price`) uses that mutable field. In practice this rarely matters (order items aren't normally re-saved after creation), but it means `price` is not a reliable historical snapshot the way `price_at_order` is — use `price_at_order` when you need the price actually charged.

## Order Vouchers

**Location:** `apps/voucher/models.py::OrderVoucher` (not `apps/orders/models.py` — it lives in the voucher app since it links `Order` and `Voucher`)

Join table tracking which vouchers were applied to each order: `order`, `voucher`, `applied_amount`, `applied_at`.

## Failed Order Attempts

**Location:** `apps/orders/models.py::FailedOrderAttempt`

Audit log of order submissions that failed validation — cart snapshot, balances at time of failure, program-pause context, and the validation errors raised. See [ORDER_VALIDATION_FIX.md](ORDER_VALIDATION_FIX.md) for full field list and how it's populated.

## Validation Logs

**Location:** `apps/log/models.py::OrderValidationLog` (subclasses the abstract `BaseLog`)

Records validation and audit events tied to an order:

| Field | Type | Description |
|-------|------|-------------|
| `participant` | ForeignKey (nullable) | Participant the log is about |
| `user` | ForeignKey (nullable) | Staff user responsible, for bypass/audit entries |
| `order` | ForeignKey (nullable) | Related order |
| `product` | ForeignKey (nullable) | Related product, when applicable |
| `message` | TextField | Detailed message |
| `log_type` | CharField | `INFO`, `WARNING`, or `ERROR` (default `INFO`) |
| `created_at` / `validated_at` | DateTimeField | Timestamps |

There is no `status` field with `success`/`warning`/`error` values — the actual field is `log_type` with choices `INFO` / `WARNING` / `ERROR`. Balance-check bypasses and charitable-order confirmations write a `WARNING` entry here (see `Order._consume_vouchers()`); ordinary validation failures raised from `Order.clean()` write plain (default `INFO`) entries.

## Viewing Order History

### Admin

Django admin (`/admin/orders/order/`) is still registered — `core/urls.py` keeps `path('admin/', admin.site.urls)` — but the primary staff tooling has moved to the React admin app in `frontend/`, which talks to the REST API (`/api/v1/orders/`, `/api/v1/validation-logs/`, `/api/v1/failed-order-attempts/`).

`OrderAdmin` (`apps/orders/admin.py`) shows `order_number`, `updated_at`, total price, and `paid`, with a single `OrderItemInline` — there is **no** validation-log inline. `CombinedOrder` and `FailedOrderAttempt` each have their own registered admin classes.

Via the API, `OrderViewSet` supports filtering/search/ordering (`apps/orders/api/filters.py::OrderFilter`), bulk status transitions (`bulk_update_status`), and staff-only analytics actions (`product-consumption`, `product-consumption-trends`, `failure-analytics`, `recent-failures`).

### Participant View

- The legacy server-rendered dashboard (`apps/lifeskills/views.py::participant_dashboard` → `apps/pantry/templates/food_orders/participant_dashboard.html`) lists a participant's orders alongside their account balance and order-window status.
- The current participant-facing app is the React SPA in `participant-frontend/` — `features/orders/OrderHistory.tsx` fetches `GET /api/v1/orders/?me=true` and renders each order via `OrderCard.tsx`.

## Combined Orders

Multiple confirmed orders can be combined for a program, optionally split across packers. See [COMBINED_ORDER_FEATURE.md](COMBINED_ORDER_FEATURE.md) for details.

## Related Documentation

- [ORDER_VALIDATION_FIX.md](ORDER_VALIDATION_FIX.md) — Failed-attempt logging, idempotency, throttling
- [ORDER_WINDOW_FEATURE.md](ORDER_WINDOW_FEATURE.md) — When orders can be placed
- [COMBINED_ORDER_FEATURE.md](COMBINED_ORDER_FEATURE.md) — Order combining
- [PRODUCT_ORDERING.md](PRODUCT_ORDERING.md) — Placing orders
