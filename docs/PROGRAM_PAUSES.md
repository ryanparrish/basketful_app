# Program Pauses

> Last updated: January 2026

This document describes the program pause functionality.

## Overview

Program pauses allow administrators to temporarily suspend normal voucher operations, typically during holidays or program breaks.

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
