# Combined Order Creation Feature

> Last updated: 2026-07-13

## Overview

This feature lets staff create combined orders by picking a program and a date range,
splitting the resulting warehouse/packing work across one or more packers. This provides
more flexibility than the automated weekly combined-order task
(`apps/orders/tasks/weekly_orders.py` → `combined_order_helper.process_all_programs`),
which still runs on its own schedule and produces a parent/child `CombinedOrder` hierarchy
for the current week. The manual flow described here creates a single flat `CombinedOrder`
with its own `PackingList` records instead.

Both the staff React admin and the Django admin expose this workflow; they call the same
backend functions, so results are equivalent either way.

## How to Use

### React Admin (primary UI)

`frontend/src/pages/CreateCombinedOrder.tsx` is a 4-step wizard (Configure → Preview →
Creating → Success):

1. **Configure**: pick a **Program** (every program in the system is listed — there is no
   "active programs only" filter) and a **Start Date** / **End Date**.
2. **Preview** (`POST /api/v1/combined-orders/preview/`): shows eligible/excluded order
   counts, totals by category, and — if the program has more than one packer — a preview
   of how orders will be split.
3. **Create** (`POST /api/v1/combined-orders/create-with-packing/`): creates the
   `CombinedOrder` and its `PackingList`s.
4. **Success**: download links for the primary order PDF, the ZIP of all packing lists,
   and each individual packing list.

### Django Admin (equivalent, legacy path)

1. Log in to `/admin/`, navigate to **Orders → Combined Orders**.
2. Click **"Create Combined Order"** — a 4-step flow (`create/` → `preview/` → `confirm/`
   → `<pk>/success/`) backed by the same `apps/orders/tasks/helper/combined_order_helper.py`
   functions as the React wizard, using the session to carry state between steps.

## What Gets Combined

`combined_order_helper.get_eligible_orders(program, start_date, end_date, status='confirmed')`:
- **Only confirmed orders** (`status='confirmed'`)
- **Orders for the selected program** (via `order.account.participant.program`)
- **Orders within the date range** (matched against `order_date`, inclusive of both ends)
- Orders already attached to another `CombinedOrder` are **excluded** (surfaced as a
  warning, not an error — the rest of the eligible orders still proceed)

If no eligible orders are found, the preview reports an error and creation is blocked.

## Split Strategies

Every program has a `default_split_strategy` (`apps/lifeskills/models.py::Program`); the
create form/wizard can override it per combined order. Choices
(`CombinedOrder.SPLIT_STRATEGY_CHOICES`):

| Strategy | Behavior |
|----------|----------|
| `none` | Single packer — one `PackingList` with every order. |
| `fifty_fifty` | Orders split into roughly equal halves across exactly 2 packers. |
| `round_robin` | Orders alternated across all of the program's packers. |
| `by_category` | Each packer gets *every* order but only the categories assigned to them via `PackingSplitRule`. |

`combined_order_helper.validate_split_strategy(program, strategy)` enforces the
prerequisites before allowing creation: the program must have at least one packer
(`apps.pantry.models.OrderPacker`, assigned via its `programs` M2M); `fifty_fifty` needs at
least 2 packers; `by_category` needs at least one `PackingSplitRule` with categories
assigned.

## Technical Details

### Key Models (`apps/orders/models.py`)

- **`CombinedOrder`** — `program`, `orders` (M2M), `split_strategy`, `week`/`year`
  (auto-populated **from the creation time**, not from the selected date range — this
  means two combined orders can't be created for the same program in the same ISO week,
  enforced by the `unique_program_per_week` constraint, even if their source date ranges
  don't overlap), `is_parent` (set by the automated weekly task, `False` for
  manually-created ones), `summarized_data`.
- **`PackingSplitRule`** — maps a `(program, packer)` pair to the `categories`/`subcategories`
  that packer is responsible for; used for the `by_category` strategy.
- **`PackingList`** — one per packer per `CombinedOrder`, holding its assigned `orders`,
  `categories` (for `by_category`), and cached `summarized_data`.

### Key Functions (`apps/orders/tasks/helper/combined_order_helper.py`)

- `get_eligible_orders(program, start_date, end_date, status='confirmed')`
- `validate_split_strategy(program, strategy)`
- `get_split_preview(orders, program, strategy)` — used by the preview step
- `create_combined_order_with_packing(program, orders, strategy, name=None)` — creates the
  `CombinedOrder` and its `PackingList`s in one atomic transaction
- `uncombine_order(combined_order)` — clears `PackingList`s and the `orders` M2M (called
  before deleting the `CombinedOrder`)

### API Endpoints (`apps/orders/api/views.py::CombinedOrderViewSet`)

- `POST /api/v1/combined-orders/preview/`
- `POST /api/v1/combined-orders/create-with-packing/`
- `POST /api/v1/combined-orders/{id}/uncombine/`
- `GET /api/v1/combined-orders/{id}/download-primary-pdf/`
- `GET /api/v1/combined-orders/{id}/download-packing-list-pdf/`
- `GET /api/v1/combined-orders/{id}/download-all-packing-lists/`
- `GET /api/v1/packing-lists/{id}/download-pdf/`

### Django Form (legacy path)

`apps/orders/forms.py::CreateCombinedOrderForm` — fields `program` (all programs, not
filtered), `start_date`, `end_date`, `split_strategy_override`. Validates `start_date <=
end_date`.

## Benefits

- **Flexibility**: create combined orders for any time period, not just the current week
- **Program-specific**: target specific programs for order combination
- **Packer-aware**: automatically splits work across a program's packers using its
  configured strategy, with a preview before committing
- **Two front doors**: the same backend logic is reachable from the React admin wizard or
  the Django admin, so either can be used interchangeably
