# Program Pauses

> Last updated: 2026-10-17

This document describes the program pause functionality.

## Overview

Program pauses (`apps/lifeskills/models.py::ProgramPause`) represent a scheduled break in program meetings (holidays, staff breaks, etc.). They have two distinct effects, active during two different windows:

1. **Pre-pause ordering window (10–14 days before `pause_start`):** grocery vouchers — and, by extension, the Go Fresh budget (see [GO_FRESH_BUDGET_FEATURE.md](GO_FRESH_BUDGET_FEATURE.md)) — get a multiplier boost (2x or 3x) so participants can stock up before the break. This is what the `multiplier` / `is_active_gate` properties describe.
2. **The pause itself (`pause_start` to `pause_end`):** ordering is blocked entirely for every program, full stop — this is a hard gate on order creation, not a balance restriction. Staff can force a program's order window back open with a `ProgramWindowOverride` (see `core/models.py`) as an escape hatch.

These are deliberately separate mechanisms — see `core/utils.py::get_in_progress_pause()`'s docstring, which spells out that the in-progress check uses the raw `pause_start`/`pause_end` range and *not* `is_active_gate`/`multiplier`, because those are only true during the pre-pause window and are always false once the pause has actually started.

## Business Rule: Ordering Window

Programs meet weekly on a fixed night (e.g., Thursday evenings). When a program pause is approaching, participants must receive a larger food budget the **week before** the pause begins so they have enough food during the break.

**How it works:**

- The voucher multiplier activates **10–14 days before** the pause start date
- This window is wide enough to guarantee the program's weekly meeting night is always included, regardless of which day of the week the pause starts
- **Example:** Pause starts Sunday 3/29. Program meets Thursday 3/19 (10 days before). The 10-day lower bound ensures participants ordering that Thursday night receive the multiplier.
- The 14-day upper bound prevents the multiplier from firing two program nights early

**Why 10 days (not 11):**

The original window started at 11 days. A Thursday-night program with a Sunday pause start falls exactly 10 days before — outside the old window. Extending to 10 days covers this case without widening the window so much that two consecutive program nights would both be affected.

## Timezone Handling

### Current Implementation (EST-Specific)

All program pause date calculations use **EST (America/New_York) timezone** for consistency:

- **Ordering Window Detection:** 10-14 days before pause start
- **Date Comparisons:** Convert both `pause_start` and `now()` to EST before calculating days
- **Helper Function:** `apps.lifeskills.utils.get_est_date()`

### Why EST Conversion Matters

**Problem Example:**
```
UTC Time: 2026-03-18 03:00:00 (3 AM)
EST Time: 2026-03-17 23:00:00 (11 PM, previous day!)

Without conversion:
- System calculates days_until_start using March 18 (UTC)
- Actual ordering window should be based on March 17 (EST)
- Result: Off-by-one day error near midnight UTC
```

**Solution:**
```python
from apps.lifeskills.utils import get_est_date

today_est = get_est_date()  # Always EST date
pause_start_est = get_est_date(program_pause.pause_start)
days_until_start = (pause_start_est - today_est).days
```

### ⚠️ Multi-Timezone Expansion Path

**Current Limitation:** System assumes ALL participants are in EST.

**If you need to support PST (or other timezones):**

1. **Add Timezone Field to Model:**
   ```python
   # In apps/lifeskills/models.py
   class Program(models.Model):
       # ... existing fields ...
       timezone = models.CharField(
           max_length=50,
           default='America/New_York',
           choices=[
               ('America/New_York', 'Eastern Time'),
               ('America/Los_Angeles', 'Pacific Time'),
               ('America/Chicago', 'Central Time'),
               ('America/Denver', 'Mountain Time'),
           ],
           help_text="Timezone for this program's schedule and ordering windows"
       )
   ```

2. **Update Helper Function:**
   ```python
   def get_localized_date(dt=None, tz_string='America/New_York'):
       """Get date in specified timezone (replaces get_est_date)."""
       if dt is None:
           dt = timezone.now()
       local_tz = zoneinfo.ZoneInfo(tz_string)
       local_dt = dt.astimezone(local_tz)
       return local_dt.date()
   ```

3. **Update All Calculation Locations:**
   - Pass `program.timezone` or `participant.program.timezone` to helper
   - Update models.py, signals.py, tasks/program_pause.py
   - See code comments marked with `⚠️ EST-specific`

### Code Locations Using Timezone Logic

| File | Purpose | EST Conversion |
|------|---------|----------------|
| `apps/lifeskills/models.py` | `_calculate_pause_status()` | ✅ Yes |
| `apps/lifeskills/signals.py` | Signal handler window check | ✅ Yes |
| `apps/lifeskills/tasks/program_pause.py` | Task window validation | ✅ Yes |
| `apps/lifeskills/queryset.py` | DB annotation (limitation) | ⚠️ Documented |

## ProgramPause Model

**Location:** `apps/lifeskills/models.py::ProgramPause`

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `pause_start` | DateTimeField | When pause begins |
| `pause_end` | DateTimeField | When pause ends |
| `reason` | CharField(255), nullable | Description of pause reason |
| `archived` | BooleanField (default False) | Whether the pause has completed cleanup and is hidden from the default manager |
| `archived_at` | DateTimeField, nullable | When the pause was archived |
| `last_resync_at` / `last_resync_by_username` | DateTimeField / CharField, nullable | Retired with the Resync button (#141); unused, dropped in a follow-up migration |

`is_active_gate` and `multiplier` are **not stored fields** — they are computed `@property` methods (see below). `ProgramPause.objects` (the default manager) excludes archived pauses; use `ProgramPause.objects.all_pauses()` to include them.

### Computed Properties

- **`multiplier` (int):** Calls `_calculate_pause_status()`, which converts `pause_start` and "now" to EST dates and returns:
  - `2` if `10 <= days_until_start <= 14` and the pause is shorter than 14 days ("short pause")
  - `3` if `10 <= days_until_start <= 14` and the pause is 14+ days ("extended pause")
  - `1` otherwise — including at any point during or after the pause itself, since `days_until_start` is negative once `pause_start` has passed
- **`is_active_gate` (bool):** `True` when `multiplier > 1` — i.e., only during the 10–14 day pre-pause window, never during the pause itself

### Class Methods

- **`calculate_multiplier_for_duration(pause_start, pause_end)`:** Pure function version of the duration → multiplier logic above (2 for <14 days, 3 for ≥14 days)
- **`archive()` / `unarchive()`:** set or clear `archived`/`archived_at`. Nothing else changes: readers compute the multiplier live, so an archived pause stops counting immediately and an unarchived one counts again if it is still in its window

## Two Separate Mechanisms

### 1. Pre-Pause Ordering Window — Voucher/Go Fresh Multiplier Boost

During the 10–14 day window before `pause_start`, the pause multiplier is 2 (or 3 for an extended pause). Nothing is stored or scheduled to make this happen: every reader computes it live from `apps/lifeskills/utils.py::active_pause()`, which returns the non-archived pause currently in its window (if two overlap, the higher multiplier wins, then the earlier start). `current_pause_multiplier()` returns its multiplier, or 1.

Readers of the live multiplier:

- `calculate_available_balance()` and `calculate_go_fresh_balance()` (`apps/account/utils/balance_utils.py`) — a genuine budget increase, not a restriction
- `CategoryLimitValidator._get_active_pause_multiplier()` — category limits, and `Order.pause_multiplier_at_creation` when an order is placed
- The admin voucher screens — `pause_multiplier` on the voucher API (applied grocery vouchers only), looked up once per response
- `FailedOrderAttempt.program_pause_active` / `voucher_multiplier` / `program_pause_name`

Vouchers used to carry a copy of this state (`program_pause_flag` / `multiplier`), kept in sync by Celery tasks and a manual Resync button. Every sync path was a chance to drift (#100, #121), so #141 retired them.

At confirmation, `Order._consume_vouchers()` uses the multiplier recorded on the order when it was placed (`Order.pause_multiplier_at_creation`), so an order placed in the double-order window and confirmed after it closes is consumed at the multiplier it was validated against.

The nightly `archive_ended_pauses` task (3 AM, Celery beat) archives pauses whose `pause_end` has passed.

### 2. During the Pause — Hard Order Block

While `pause_start <= now <= pause_end` (checked via `ProgramPause.objects.in_progress()` / `core/utils.py::get_in_progress_pause()`), ordering is blocked for **every** participant regardless of program, voucher balance, or flags:

- `apps/orders/utils/order_validation.py::OrderValidation.enforce_program_pause()` raises a `ValidationError` ("Ordering is unavailable during the program pause...") as Step 0 of `validate_order_items()`
- The `validate-cart` API action (`apps/orders/api/views.py`) appends a blocking `{'type': 'window', ...}` violation
- **Escape hatch:** if the participant's `Program` has an unexpired `ProgramWindowOverride` (`core/models.py`) with `force_status='open'`, the block is skipped and ordering is allowed even mid-pause

## Checking Pause Status

```python
from apps.lifeskills.models import ProgramPause
from core.utils import get_in_progress_pause

# Is a pause's off-week happening right now? (hard order block)
in_progress_pause = get_in_progress_pause()  # or ProgramPause.objects.in_progress().first()
is_ordering_blocked = in_progress_pause is not None

# Is any pause currently in its pre-pause multiplier window?
from apps.lifeskills.utils import active_pause, current_pause_multiplier
pause = active_pause()            # ProgramPause or None
multiplier = current_pause_multiplier()  # 2 or 3 during a double week, else 1
```

## Admin Interface

Program pauses are managed via Django Admin at `/admin/lifeskills/programpause/` (`apps/lifeskills/admin.py::ProgramPauseAdmin`):

- List view shows `reason`, `pause_start`, `pause_end`, `is_active_gate`, and an archived/active status column; filterable by `archived`
- `get_queryset()` overridden to show both archived and active pauses (the default manager hides archived ones elsewhere)
- Deletion is disabled entirely (`has_delete_permission` returns `False`) — use the **Archive selected pauses** / **Unarchive selected pauses** admin actions instead, which call `ProgramPause.archive()` / `unarchive()`
- The changelist displays an info banner ("`<reason>` — This Pause Is Active") when any non-archived pause currently has `is_active_gate=True`
- `ProgramPause.clean()` (run via `full_clean()`) rejects invalid pauses: end before start, `pause_start` less than 10 days out, duration over 14 days, or overlapping an existing pause

## Related Documentation

- [ACCOUNT_BALANCES.md](ACCOUNT_BALANCES.md) — Balance calculations
- [VOUCHER_SYSTEM.md](VOUCHER_SYSTEM.md) — Vouchers
