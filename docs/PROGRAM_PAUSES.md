# Program Pauses

> Last updated: March 2026

This document describes the program pause functionality.

## Overview

Program pauses allow administrators to temporarily suspend normal voucher operations, typically during holidays or program breaks.

## Timezone Handling

### Current Implementation (EST-Specific)

All program pause date calculations use **EST (America/New_York) timezone** for consistency:

- **Ordering Window Detection:** 11-14 days before pause start
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
| `is_active_gate` | BooleanField | Whether gate logic is active |
| `reason` | TextField | Description of pause reason |

## Pause Types

### Standard Pause
A period where the program is paused. Vouchers may still be available depending on their flags.

### Gate Pause (`is_active_gate=True`)
When a pause has `is_active_gate=True`, only vouchers with `program_pause_flag=True` are included in available balance calculations.

## Effects on Balances

During an active gate pause:

```python
# Normal operation
available_balance = sum(oldest 2 applied vouchers)

# During gate pause
available_balance = sum(oldest 2 applied vouchers WHERE program_pause_flag=True)
```

**Implementation:** `apps/account/utils/balance_utils.py::calculate_available_balance()`

## Voucher Pause Flag

Each voucher has a `program_pause_flag` field:

- `True` — Voucher remains available during gate pauses
- `False` — Voucher excluded during gate pauses

This allows administrators to issue special vouchers that work during pauses (e.g., emergency food vouchers).

## Checking Pause Status

```python
from django.utils import timezone
from apps.lifeskills.models import ProgramPause

now = timezone.now()
active_pauses = ProgramPause.objects.filter(
    pause_start__lte=now,
    pause_end__gte=now
)
is_paused = active_pauses.exists()
is_gated = any(p.is_active_gate for p in active_pauses)
```

## Admin Interface

Program pauses are managed via Django Admin at `/admin/lifeskills/programpause/`

## Related Documentation

- [ACCOUNT_BALANCES.md](ACCOUNT_BALANCES.md) — Balance calculations
- [VOUCHER_SYSTEM.md](VOUCHER_SYSTEM.md) — Voucher flags
- [SIGNALS_AUTOMATION.md](SIGNALS_AUTOMATION.md) — Automated pause handling
