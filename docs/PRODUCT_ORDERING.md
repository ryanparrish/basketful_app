# Product Ordering

> Last updated: 2026-07-13

This document describes the product catalog and ordering flow.

## Overview

The ordering system lets participants browse products by category and build a cart within
their available balance limits. There are two parallel client implementations against the
same backend rules — see [Client Implementations](#client-implementations) below.

## Product Model

**Location:** `apps/pantry/models.py::Product`

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | CharField | Product display name |
| `price` | DecimalField | Unit price |
| `category` | ForeignKey (nullable) | Product category (`SET_NULL` on delete) |
| `subcategory` | ForeignKey (nullable) | Product subcategory (`SET_NULL` on delete) |
| `tags` | ManyToMany | Product tags for search/filtering |
| `active` | BooleanField | Whether product is available (field is `active`, not `is_active`) |
| `quantity_in_stock` | IntegerField | Current stock, floored at 0 |
| `is_meat` | BooleanField | Flags meat products |
| `weight_lbs` | DecimalField | Weight, e.g. for meat portioning |
| `sort_order` | IntegerField | Pick sequence for packing lists |
| `low_stock_alerted_at` | DateTimeField (nullable) | Set/cleared by the low-inventory alert task |

## Categories

**Location:** `apps/pantry/models.py::Category`

Fields: `name`, `sort_order`. Categories don't carry a stored "balance rule" flag — instead,
`Order.clean()` and the `validate-cart` API action recognize the **Hygiene** and **Go
Fresh** categories by matching `category.name.lower()`, and apply the participant's
`hygiene_balance` / `go_fresh_balance` accordingly. Everything else counts against the
general `available_balance`.

### Protected Categories

`apps/pantry/admin.py::CategoryAdmin` protects any category whose name matches
`PROTECTED_CATEGORIES` (currently "hygiene" and "go fresh", case-insensitive): the `name`
field becomes read-only and deletion is blocked (`has_delete_permission` /
`delete_model` raise `PermissionDenied`). See `apps/pantry/tests/test_category_protection.py`.

## Cart Validation

Validation happens in two layers that share the same rules:

- **`Order.clean()`** (`apps/orders/models.py`) — runs on every save when `status ==
  "confirmed"`: duplicate-active-order guard, food/hygiene/Go Fresh balance checks,
  `CategoryLimitValidator.validate_category_limits()` (per-category quantity limits, scoped
  per adult/child/infant/household/order, with a program-pause multiplier applied), and
  voucher-total validation.
- **`OrderViewSet.validate_cart`** (`POST /api/v1/orders/validate-cart/`) — the
  pre-checkout validation used by the participant frontend. It builds a temporary `Order`
  + `OrderItem`s inside a transaction that is **always rolled back** (nothing is persisted),
  runs the same balance/limit checks, additionally blocks ordering during an in-progress
  program pause (`core.utils.get_in_progress_pause` / `get_active_window_override`), and
  applies a **grace allowance**: if the overage is within `ProgramSettings.grace_amount`
  (default $1.00) and `grace_enabled` is on, the violation is downgraded from `error` to
  `warning` with an educational message (`ProgramSettings.grace_message`) instead of
  blocking checkout. `ProgramSettings` (`core/models.py`) is configured via the admin and
  is the single source for this — it is not covered in [ACCOUNT_BALANCES.md](ACCOUNT_BALANCES.md).

`OrderOrchestration.create_order()` (`apps/orders/utils/order_utils.py`) runs the real
validation (via `OrderValidation.validate_order_items`) before writing anything to the
database, so a failed submission never leaves an orphaned `pending` `Order` row — see
[ORDER_VALIDATION_FIX.md](ORDER_VALIDATION_FIX.md).

## Client Implementations

### React Participant Frontend (primary)

`participant-frontend/` is a single-page app that talks to the REST API:

- `ProductsPage.tsx` / `CategoryTabs.tsx` / `ProductGrid.tsx` — browse via
  `GET /api/v1/products/` and `GET /api/v1/categories/`
- `CartProvider.tsx` / `CartDrawer.tsx` / `CartItem.tsx` — client-side cart state, validated
  live via `useCartValidation` (calls `validate-cart`)
- `CheckoutPage.tsx` — final review; checks `useOrderWindow()` before allowing submit,
  then calls `POST /api/v1/orders/` (`createOrder`)
- `OrderHistory.tsx` / `OrderCard.tsx` — past orders via `GET /api/v1/orders/?me=true`

### Legacy Django Views (session-cart based)

- **Browse**: `apps/pantry/views.py::product_view` → `pantry/create_order.html`
  (template lives at `core/templates/pantry/create_order.html`, not under
  `apps/pantry/templates/`)
- **Add to Cart**: `apps/pantry/views.py::update_cart` (AJAX, session-backed cart)
- **Review / Submit**: `apps/orders/views.py::review_order` / `submit_order` →
  `OrderOrchestration.create_order()`
- **Confirm**: staff confirm via Django admin or the API; vouchers are consumed and stock
  decremented in `Order.confirm()`

## Ordering Flow (both clients)

1. **Browse** — participant views active products by category
2. **Add to Cart** — products added with quantity validation
3. **Validate** — cart checked against available balances, category limits, and (for the
   React app) the order window / grace allowance, without writing to the database
4. **Submit Order** — order created in `pending` state (validated first, so a failure
   never leaves a stray row)
5. **Confirm** — staff confirms (or, for the React flow, the legacy view auto-confirms
   immediately after creation); vouchers consumed, stock decremented

## Order Window

Orders can only be placed during a configured order window (global default, optional
per-program override, manual force-open/close, and blocked entirely during an in-progress
program pause). See [ORDER_WINDOW_FEATURE.md](ORDER_WINDOW_FEATURE.md) for details.

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — System overview
- [ACCOUNT_BALANCES.md](ACCOUNT_BALANCES.md) — Balance constraints and grace allowance
- [ORDER_WINDOW_FEATURE.md](ORDER_WINDOW_FEATURE.md) — Ordering schedule
- [GO_FRESH_BUDGET_FEATURE.md](GO_FRESH_BUDGET_FEATURE.md) — Fresh food budget
- [ORDER_VALIDATION_FIX.md](ORDER_VALIDATION_FIX.md) — Validation-before-write, idempotency, throttling
- [ORDER_HISTORY.md](ORDER_HISTORY.md) — Order model and viewing order history
