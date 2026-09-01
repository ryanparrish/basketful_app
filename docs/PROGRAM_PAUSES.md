# Program Pauses

> Last updated: 2026-07-13

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
| `last_resync_at` / `last_resync_by_username` | DateTimeField / CharField, nullable | Bookkeeping for manual re-syncs of voucher flags |

`is_active_gate` and `multiplier` are **not stored fields** — they are computed `@property` methods (see below). `ProgramPause.objects` (the default manager) excludes archived pauses; use `ProgramPause.objects.all_pauses()` to include them.

### Computed Properties

- **`multiplier` (int):** Calls `_calculate_pause_status()`, which converts `pause_start` and "now" to EST dates and returns:
  - `2` if `10 <= days_until_start <= 14` and the pause is shorter than 14 days ("short pause")
  - `3` if `10 <= days_until_start <= 14` and the pause is 14+ days ("extended pause")
  - `1` otherwise — including at any point during or after the pause itself, since `days_until_start` is negative once `pause_start` has passed
- **`is_active_gate` (bool):** `True` when `multiplier > 1` — i.e., only during the 10–14 day pre-pause window, never during the pause itself

### Class Methods

- **`calculate_multiplier_for_duration(pause_start, pause_end)`:** Pure function version of the duration → multiplier logic above (2 for <14 days, 3 for ≥14 days), used by both the immediate-flagging signal path and the scheduled-task path so they stay consistent
- **`archive()` / `unarchive()`:** `archive()` resets any vouchers still flagged for this pause (`program_pause_flag=False`, `multiplier=1`) and sets `archived=True`/`archived_at=now()`; `unarchive()` clears those fields (a subsequent save re-triggers the pause signal if the window is still active)

## Two Separate Mechanisms

### 1. Pre-Pause Ordering Window — Voucher/Go Fresh Multiplier Boost

During the 10–14 day window before `pause_start`, the `post_save` signal in `apps/lifeskills/signals.py::handle_program_pause()` flags every active voucher (`program_pause_flag=True`) with `multiplier=2` or `multiplier=3` (via `apps.lifeskills.tasks.program_pause.update_voucher_flag_task`). If the pause is created outside that window, `schedule_voucher_tasks()` schedules the same flagging for `pause_start` instead of doing it immediately.

`calculate_available_balance()` (`apps/account/utils/balance_utils.py`) always multiplies each selected voucher's amount by that voucher's own `multiplier` field, so a flagged voucher counts double or triple toward available balance **for the duration it stays flagged** — this is a genuine budget increase, not a restriction. `calculate_go_fresh_balance()` applies the same boost via `_get_current_pause_multiplier()`, which takes the highest `multiplier` across all non-archived pauses.

`calculate_available_balance()` also has a `gate_active` code path that restricts the voucher selection to `program_pause_flag=True` vouchers whenever a pause is `is_active_gate` **and** currently in progress (`pause_start <= now <= pause_end`). In practice this filter never engages: `is_active_gate` requires `10 <= days_until_start <= 14`, which is impossible once `pause_start` has already passed. This is called out explicitly in `core/utils.py::get_in_progress_pause()`'s docstring. Voucher flags get cleared automatically once the participant's own order window closes (`deactivate_expired_pause_vouchers` task) or, at the latest, after `pause_end` (`final_cleanup_after_pause_end`, which also archives the pause) or via the daily `cleanup_expired_pause_flags` safety-net task.

### 2. During the Pause — Hard Order Block

While `pause_start <= now <= pause_end` (checked via `ProgramPause.objects.in_progress()` / `core/utils.py::get_in_progress_pause()`), ordering is blocked for **every** participant regardless of program, voucher balance, or flags:

- `apps/orders/utils/order_validation.py::OrderValidation.enforce_program_pause()` raises a `ValidationError` ("Ordering is unavailable during the program pause...") as Step 0 of `validate_order_items()`
- The `validate-cart` API action (`apps/orders/api/views.py`) appends a blocking `{'type': 'window', ...}` violation
- **Escape hatch:** if the participant's `Program` has an unexpired `ProgramWindowOverride` (`core/models.py`) with `force_status='open'`, the block is skipped and ordering is allowed even mid-pause

## Voucher Pause Flag

Each voucher (`apps/voucher/models.py::Voucher`) has two related fields:

- `program_pause_flag` (BooleanField, default `False`) — whether this voucher is currently flagged as part of an active pre-pause window
- `multiplier` (IntegerField, default `1`, not user-editable) — the multiplier applied to this voucher's amount in balance calculations; set to `2` or `3` alongside the flag, reset to `1` when cleared

Flags/multipliers are set and cleared idempotently by `apps/lifeskills/utils.py::set_voucher_pause_state()`, which is used by the immediate-flagging signal, the scheduled activation/deactivation tasks, and `ProgramPause.archive()`.

## Checking Pause Status

```python
from apps.lifeskills.models import ProgramPause
from core.utils import get_in_progress_pause

# Is a pause's off-week happening right now? (hard order block)
in_progress_pause = get_in_progress_pause()  # or ProgramPause.objects.in_progress().first()
is_ordering_blocked = in_progress_pause is not None

# Is any pause currently in its pre-pause multiplier window?
# (is_active_gate/multiplier are properties, evaluated in Python, not queryable in SQL)
boosted_pauses = [p for p in ProgramPause.objects.all() if p.is_active_gate]
current_multiplier = max((p.multiplier for p in boosted_pauses), default=1)
```

## Admin Interface

Program pauses are managed via Django Admin at `/admin/lifeskills/programpause/` (`apps/lifeskills/admin.py::ProgramPauseAdmin`):

- List view shows `reason`, `pause_start`, `pause_end`, `is_active_gate`, and an archived/active status column; filterable by `archived`
- `get_queryset()` overridden to show both archived and active pauses (the default manager hides archived ones elsewhere)
- Deletion is disabled entirely (`has_delete_permission` returns `False`) — use the **Archive selected pauses** / **Unarchive selected pauses** admin actions instead, which call `ProgramPause.archive()` / `unarchive()`
- The changelist displays an info banner ("`<reason>` — This Pause Is Active") when any non-archived pause currently has `is_active_gate=True`
- `ProgramPause.clean()` (run via `full_clean()`) rejects invalid pauses: end before start, `pause_start` less than 10 days out, duration over 14 days, or overlapping an existing pause

### Manual Cleanup Command

`python manage.py run_pause_cleanup <pause_id> [<pause_id> ...] [--dry-run] [--force]` (`apps/lifeskills/management/commands/run_pause_cleanup.py`) lets staff manually run `final_cleanup_after_pause_end` for a pause — useful if a Celery `eta` task was missed (broker outage) or to preview/force a voucher reset without waiting for the scheduled time.

## Related Documentation

- [ACCOUNT_BALANCES.md](ACCOUNT_BALANCES.md) — Balance calculations
- [VOUCHER_SYSTEM.md](VOUCHER_SYSTEM.md) — Voucher flags
- [SIGNALS_AUTOMATION.md](SIGNALS_AUTOMATION.md) — Automated pause handling
