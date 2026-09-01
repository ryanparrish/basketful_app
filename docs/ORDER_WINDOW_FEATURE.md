# Order Window Feature

> Last updated: 2026-07-13

## Overview

This feature restricts when participants can place orders based on their class schedule.
Orders can only be placed within a configurable window before their scheduled class time.
The window is resolved from three layers, each overriding the one before it:

1. A **global default** (`core.models.OrderWindowSettings`, singleton).
2. An optional **per-program override** (`core.models.ProgramOrderWindow`) — any of its
   fields can be left blank to fall back to the global default for that field only.
3. A **manual force-open / force-closed override** (`core.models.ProgramWindowOverride`)
   that staff can push for a single program until an explicit expiry time — this beats
   both of the above.

Independently of all three, an **in-progress Program Pause** (`apps.lifeskills.models.ProgramPause`)
blocks ordering for *every* program while the pause is underway, unless staff have
force-opened that specific program (Issue #78 — the pause week is a no-order week).

## Admin Configuration

### Global Default

Configured via `core.models.OrderWindowSettings` (singleton, admin-registered as
"Order Window Setting"):

- **Hours Before Class** (`hours_before_class`): how many hours before class time the
  window opens (1–168 hours, default 24).
- **Hours Before Close** (`hours_before_close`): how many hours before class time the
  window *closes* (0–168 hours, default 0 = closes exactly at class time).
- **Enabled** (`enabled`): toggle to disable window restrictions entirely (orders always
  allowed when off).

**Example**: hours_before_class=24, hours_before_close=2, class is Wednesday at 2:00 PM:
- Order window opens: Tuesday at 2:00 PM
- Order window closes: Wednesday at 12:00 PM (2 hours before class)

### Per-Program Override

`core.models.ProgramOrderWindow` is a sparse, one-row-per-program override — `hours_before_class`,
`hours_before_close`, and `enabled` are each nullable, and `null` means "inherit the global
value for this field." `core/utils.py::get_effective_config(program)` resolves the COALESCE
and reports which source (`'program'` or `'global'`) won for each field.

Managed via the staff React admin's **Order Window Dashboard**
(`frontend/src/pages/settings/components/order-window/`), which calls:
- `GET/PUT/DELETE /api/v1/programs/{id}/order-window/` — read/upsert/clear the override
- `GET /api/v1/order-windows/status/` — live status for every program, polled every 30s

### Manual Force-Open / Force-Close

`core.models.ProgramWindowOverride` lets staff push a single program into `force_open` or
`force_closed` until an explicit `expires_at`. Expired overrides are deleted lazily the
next time they're read (`core/utils.py::get_active_window_override`) and swept up nightly
by a Celery beat task. Managed via `POST/DELETE /api/v1/programs/{id}/order-window/override/`.

## User Experience

### Participant Frontend (React SPA)

`participant-frontend/src/shared/hooks/useOrderWindow.ts` polls
`GET /api/v1/settings/my-window/` every 60 seconds (and immediately on tab focus), and
drives a live countdown from the `seconds_until_change` the API returns. `CheckoutPage.tsx`
disables the submit button and shows an `Alert` whose message depends on `windowStatus`:
`force_closed`, `no_schedule`, `paused` (program pause in progress), or the generic
`windowClosed` message.

### Legacy Django Dashboard

`apps/lifeskills/views.py::participant_dashboard` calls `core.utils.can_place_order(participant)`
and passes the `(can_order, context)` result into `food_orders/participant_dashboard.html`
and `food_orders/order_detail.html`, which use it to disable the "Place a New Order" /
"Duplicate this order" actions and show timing information (next class, when the window
opens/closes, hours remaining).

## Technical Implementation

### Key Files

1. **`core/models.py`** — `OrderWindowSettings` (global singleton), `ProgramOrderWindow`
   (per-program sparse override), `ProgramWindowOverride` (force-open/closed)
2. **`core/admin.py`** — Django admin for `OrderWindowSettings`
3. **`core/utils.py`** — all window-resolution logic (see functions below)
4. **`apps/lifeskills/api/views.py`** — `ProgramViewSet.order_window` / `.window_override`
   actions; `CoachViewSet` dashboard action also surfaces `get_program_window_status`
5. **`core/api/views.py`** — `MyWindowView` (`/api/v1/settings/my-window/`) and
   `OrderWindowDashboardView` (`/api/v1/order-windows/status/`)
6. **`apps/lifeskills/tests/test_order_window.py`** — test suite for order window functionality
7. **`apps/orders/views.py`** / **`apps/pantry/templates/food_orders/`** — legacy Django UI
8. **`participant-frontend/src/shared/hooks/useOrderWindow.ts`** and
   **`frontend/src/pages/settings/components/order-window/OrderWindowDashboard.tsx`** — React UIs

### Key Functions (`core/utils.py`)

#### `get_effective_config(program) -> dict`
Resolves the per-program override against the global default (COALESCE), returning the
effective `hours_before_class`, `hours_before_close`, `enabled`, and which source each
came from.

#### `generate_window_cycles(program, config, n=3) -> list`
Pure function that derives the next `n` `(opens_at, closes_at, meeting_at)` cycles from the
program's `MeetingDay` + `meeting_time` and the resolved config. Nothing is persisted.

#### `get_program_window_status(program) -> dict`
Full status snapshot for one program: checks for an active `ProgramWindowOverride` first,
then an in-progress `ProgramPause`, then the schedule-based window. Returns
`window_status` of `force_open` / `force_closed` / `paused` / `disabled` / `no_schedule` /
`open` / `closed`, plus `seconds_until_change` and the next three cycles.

#### `can_place_order(participant) -> (bool, dict)`
Participant-facing check with the same precedence (override → pause → schedule). Returns
detailed timing information for display. Used by both the legacy Django views and the
`validate-cart` API action (`apps/orders/api/views.py`) to block ordering during a program
pause.

#### `get_next_class_datetime(participant) -> datetime | None`
Calculates the next scheduled class datetime for a participant based on their program's
`MeetingDay` and `meeting_time`. Kept for backwards compatibility with `can_place_order`'s
context payload.

### Database Migrations

The order-window models live in the `core` app's migrations (`core/migrations/`):
`OrderWindowSettings` (0001), `hours_before_close` added (0002), and
`ProgramOrderWindow`/`ProgramWindowOverride` added later (0007). Run
`python manage.py migrate core` to apply.

## Testing

Run the test suite:
```bash
python -m pytest apps/lifeskills/tests/test_order_window.py -xvs
```

Tests cover: settings singleton pattern, next-class-datetime calculation, order-window
validation, context data population, disabled-window behavior, and the no-program edge case.

## Future Enhancements

Potential improvements:
- Email notifications when a window opens
- Different windows for food vs hygiene products
- Holiday/blackout date handling
