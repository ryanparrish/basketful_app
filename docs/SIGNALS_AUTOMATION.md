# Signals & Automation System

> Last updated: 2026-07-13

## Overview
Django signals provide automatic responses to model events, enabling seamless automation throughout Basketful. The system automatically handles account creation, voucher generation, user setup, coach/group sync, program-pause voucher flagging, rules-version cache invalidation, and login auditing.

Signal handlers live in `signals.py` files across six apps/modules: `apps/account`, `apps/pantry`, `apps/lifeskills`, `apps/log`, `apps/voucher`, and `core`. There is no `signals.py` in `apps/api` or `apps/orders` — order-number generation, for example, is a model `save()` override, not a signal (see [Order Number Generation](#order-number-generation-not-a-signal) below).

## Signal Types

### Post-Save Signals
Triggered after a model instance is saved.

### Pre-Save Signals
Triggered before a model instance is saved.

### Post-Delete Signals
Triggered after a model instance is deleted.

## Implemented Signals

### 1. Participant Signals

**File**: `apps/account/signals.py`

There are **three** `post_save` receivers on `Participant` in this file, plus **two** more in `apps/pantry/signals.py` (see below) — five total. Both apps' `signals.py` modules are imported from `AppConfig.ready()`, so all five fire on every `Participant` save:

#### Sync User Email on Change
```python
@receiver(post_save, sender=Participant)
def sync_user_email_on_change(instance: Participant, created, **kwargs):
    """Keep User.email in sync with Participant.email whenever it changes."""
```
**Triggers**: Participant update only (returns early if `created` or if there's no linked `user`).
**Actions**: If `update_fields` includes `email` (or is unspecified) and `user.email != participant.email`, updates `User.email` via `user.save(update_fields=['email'])`.

#### Update Base Balance on Change
```python
@receiver(post_save, sender=Participant)
def update_base_balance_on_change(instance, created, **kwargs):
    """Update AccountBalance.base_balance whenever relevant fields change."""
```
**Triggers**: Participant update only (returns early if `created`).

**Watched Fields** (only checked when `update_fields` is passed to `.save()`; if `update_fields` is `None` the recalculation always runs):
- `adults`
- `children`
- `diaper_count`

**Actions**:
1. Detect if balance-affecting fields changed
2. Recalculate `base_balance` via `calculate_base_balance()`
3. `account_balance.save(update_fields=["base_balance"])`

#### Initialize Participant
```python
@receiver(post_save, sender=Participant)
def initialize_participant(instance: Participant, created, **kwargs):
    """
    Initialize a participant after creation:
    - Create a linked User if one isn't already set
    - Create UserProfile
    - Setup account and vouchers
    - Trigger onboarding email
    """
```
**Triggers**: New participant creation only (returns early if not `created`).

**Actions**:
1. If `instance.user` isn't already set, create one via `create_participant_user()` and re-save the participant with `update_fields=['user']`
2. `UserProfile.objects.get_or_create(user=instance.user)` — this is how `UserProfile` actually gets created for participants; there is **no** standalone `post_save` receiver on `User` that creates a `UserProfile` for every user (see note under Automation Workflows)
3. Call `setup_account_and_vouchers(instance)` (in `apps/pantry/utils/voucher_utils.py`)
4. If a `User` was created by *this* signal (not pre-existing), schedule `send_new_user_onboarding_email.delay(user_id=...)` via `transaction.on_commit(...)` — unless `instance._skip_onboarding_signal` is set (bulk-create tooling handles its own onboarding email with a grace-period delay)

> **Duplicate wiring note**: `apps/pantry/signals.py` also registers `ensure_account_and_vouchers` and `init_account_and_vouchers` on `post_save, sender=Participant`, both of which call `setup_account_and_vouchers()` again. `setup_account_and_vouchers()` is idempotent (it returns immediately if `participant.accountbalance` already exists), so this is redundant-but-harmless rather than a bug, but it means a single `Participant` save fires **five** separate `post_save` receivers across two files.

### 2. Voucher Signals

**File**: `apps/voucher/signals.py`

```python
@receiver(pre_save, sender=Voucher)
def voucher_pre_save(instance, **kwargs): ...

@receiver(post_save, sender=Voucher)
def voucher_post_save(instance, created, **kwargs): ...

@receiver(pre_delete, sender=Voucher)
def voucher_pre_delete(instance, **kwargs): ...

@receiver(post_delete, sender=Voucher)
def voucher_post_delete(instance, **kwargs): ...
```

**Triggers**: Voucher create/update/delete.

**Actions**:
- `voucher_pre_save` / `voucher_pre_delete`: capture `account.full_balance` and (for updates) the previous `state`/`active` values as instance attributes, for before/after logging
- `voucher_post_save`: on create, logs an entry via `log_voucher()` (`apps.log.logging`); on update, logs only if `state` or `active` actually changed
- `voucher_post_delete`: logs a `WARNING`-level entry noting the voucher was deleted

> ⚠️ **These handlers are not currently connected.** Unlike `account`, `pantry`, `lifeskills`, `log`, and `core`, **`apps/voucher/apps.py` has no `ready()` method and never imports `apps.voucher.signals`**, and nothing else in the codebase imports that module either. Because Django only registers `@receiver`-decorated functions when their module is imported, `voucher_pre_save`/`voucher_post_save`/`voucher_pre_delete`/`voucher_post_delete` are dead code as of this writing — they do not fire. If voucher lifecycle logging is expected to work, `VoucherConfig.ready()` needs to import `apps.voucher.signals`.
>
> Program-pause voucher multipliers are **not** handled here — that logic lives in `apps/lifeskills/signals.py` (see below).

### 3. Order Number Generation (not a signal)

**File**: `apps/orders/models.py`

Order numbers are **not** generated by a Django signal. `Order.save()` is overridden directly:
```python
def save(self, *args, **kwargs):
    if self.pk is None:
        self._ensure_order_number()
    ...
```
`_ensure_order_number()` calls `_generate_order_number()`, which produces `ORD-YYYYMMDD-XXXXXX` where `XXXXXX` is 6 uppercase hex characters from `secrets.token_hex(3)` (e.g. `ORD-20260713-A1B2C3`) — not the 6-digit numeric suffix previously documented here. It retries up to 10 times to avoid a collision on the `unique=True` `order_number` field.

There is no `apps/orders/signals.py`, and `apps/pantry/signals.py` does not touch `Order` at all (see next section).

### 4. Pantry Signals (Participant/User, not Order)

**File**: `apps/pantry/signals.py`

```python
@receiver(post_save, sender=Participant)
def ensure_account_and_vouchers(instance, created, **kwargs):
    """Ensure each participant has an account and initial vouchers (every save)."""

@receiver(post_save, sender=User)
def create_staff_user_profile_and_onboarding(sender, instance, created, update_fields, **kwargs):
    """Trigger onboarding email + UserProfile for new *staff* users only."""

@receiver(post_save, sender=Participant)
def init_account_and_vouchers(sender, instance, created, **kwargs):
    """Initialize account and vouchers only for newly created participants."""
```

**Actions**:
- `ensure_account_and_vouchers`: calls `setup_account_and_vouchers(instance)` unconditionally on every `Participant` save (created or not) — overlaps with `init_account_and_vouchers` below and with `account/signals.py`'s `initialize_participant`
- `create_staff_user_profile_and_onboarding`: skips saves where `update_fields == {"last_login"}` (login events); for newly-created staff users (`created and instance.is_staff`), creates a `UserProfile` via `get_or_create` and — unless the user is a superuser — sends the onboarding email synchronously via `send_new_user_onboarding_email.delay(...)`. This is the **only** place `UserProfile` is auto-created for staff/admin `User` accounts; participant-linked users get theirs from `initialize_participant` in `apps/account/signals.py` instead
- `init_account_and_vouchers`: calls `setup_account_and_vouchers(instance)` only when `created` is `True`

### 5. Lifeskills Signals

**File**: `apps/lifeskills/signals.py`

Not previously documented. Two independent concerns:

#### Coach ↔ User Group Sync
```python
@receiver(pre_save, sender=LifeskillsCoach)
def track_coach_user_change(sender, instance, **kwargs): ...

@receiver(post_save, sender=LifeskillsCoach)
def sync_coach_user_group(sender, instance, created, **kwargs): ...
```
**Triggers**: `LifeskillsCoach` create/update.
**Actions**: `track_coach_user_change` stashes the previous `user` FK (via `pre_save`) so `sync_coach_user_group` can diff old vs. new. When the linked user changes, the old user is removed from the `'Lifeskills Coach'` group and has `is_staff` revoked (unless they're a superuser or belong to another staff-implying group: `Staff`, `Admin`). The new user is added to the `'Lifeskills Coach'` group and granted `is_staff=True`.

#### Program Pause → Voucher Flagging
```python
@receiver(post_save, sender=ProgramPause)
def handle_program_pause(sender, instance, created, **kwargs): ...
```
**Triggers**: `ProgramPause` create/update. Guarded by `instance._skip_signal` to avoid recursion.

**Actions**:
1. Finds all `Voucher` objects with `active=True, account__active=True`; exits if none
2. Converts `pause_start` to an EST calendar date (`get_est_date`) and computes `days_until_start`
3. **If 10–14 days until the pause starts**: immediately dispatches `update_voucher_flag_task.delay(voucher_ids, multiplier=..., activate=True, program_pause_id=...)` with a multiplier from `ProgramPause.calculate_multiplier_for_duration()`, then schedules `deactivate_expired_pause_vouchers.apply_async(eta=...)` for shortly after the earliest affected participant's order window closes (via `OrderWindowSettings` + `get_next_class_datetime`, plus a 5-minute buffer)
4. **Otherwise**: falls back to `schedule_voucher_tasks(vouchers, activate_time=pause_start, deactivate_time=pause_end)` for later Celery-beat-driven execution; logs a `VoucherLogger.error()` per voucher and re-raises on unexpected exceptions

> ⚠️ This module hard-codes an EST/America-New-York assumption for the ordering-window calculation (see the `⚠️` warnings in the source).

### 6. Log Signals (auth audit trail)

**File**: `apps/log/signals.py`

Not previously documented. These hook Django's built-in **auth** signals, not model signals:
```python
@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs): ...

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs): ...

@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs): ...
```
**Actions**: Each creates a `UserLoginLog` row recording the action (`LOGIN`/`LOGOUT`/`FAILED_LOGIN`), client IP (via `X-Forwarded-For` or `REMOTE_ADDR`), truncated user agent, and (where resolvable) the linked `Participant`. `log_user_login_failed` records `username_attempted` instead of a user/participant since authentication didn't succeed.

This file also defines the `VoucherLogger` helper class (`.debug()` / `.error()`), used by `apps/lifeskills/signals.py` and elsewhere to write `VoucherLog` rows.

### 7. Core Signals (rules-version cache + admin notifications)

**File**: `core/signals.py`

Not previously documented.

#### Rules Version Cache Invalidation
```python
@receiver(post_save, sender='core.ProgramSettings')
@receiver(post_save, sender='core.OrderWindowSettings')
@receiver(post_save, sender='pantry.ProductLimit')
@receiver(post_save, sender='account.GoFreshSettings')
def update_rules_version(sender, instance, **kwargs): ...
```
**Triggers**: Save of any rule-affecting model — `ProgramSettings`, `OrderWindowSettings`, `ProductLimit`, or `GoFreshSettings`.
**Actions**: Recomputes an MD5 hash (`_compute_rules_hash()`) over the current state of those four models/settings, replaces the `rules_version` cache entry (24h TTL, key `rules_version`), and back-fills `ProgramSettings.rules_version` with a `.filter(pk=...).update(...)` (chosen specifically to avoid re-triggering this same `post_save` signal recursively).

#### Grace Allowance Admin Notification
```python
@receiver(post_save, sender='log.GraceAllowanceLog')
def notify_admin_grace_usage(sender, instance, created, **kwargs): ...
```
**Triggers**: New `GraceAllowanceLog` row where `instance.proceeded` is `True` (i.e. participant went over budget and proceeded anyway).
**Actions**: Writes a Django admin `LogEntry` (`CHANGE` action) for every active staff user, noting the participant and the over-budget amount. Wrapped in a broad `try/except` that only logs a warning on failure, so it can't break the order flow.

## Automation Workflows

### New Participant Workflow

**Trigger**: Administrator creates participant

**Automatic Steps**:
1. ✅ `Participant.save()` generates `customer_number` (model method, not a signal — see `Participant.save()` in `apps/account/models.py`)
2. ✅ Participant saved to database
3. ✅ Five `post_save` receivers fire across `apps/account/signals.py` and `apps/pantry/signals.py` (see [Participant Signals](#1-participant-signals))
4. ✅ AccountBalance created (via `setup_account_and_vouchers`)
5. ✅ Base balance calculated from the active `VoucherSetting` (`adults × adult_amount + children × child_amount + diaper_count × infant_modifier`; defaults $20 / $12.50 / configurable — **no minimum floor**, returns `$0` if no active `VoucherSetting` exists)
6. ✅ 2 initial grocery vouchers created (`state="applied", active=True`)
7. ✅ Linked `User` created if the participant didn't already have one
8. ✅ UserProfile created (via `get_or_create` inside `initialize_participant`)
9. ✅ Onboarding email scheduled on commit (unless `_skip_onboarding_signal` is set for bulk-create flows)

**Result**: Fully configured participant ready to order.

### Household Change Workflow

**Trigger**: Administrator updates household size

**Automatic Steps**:
1. ✅ Participant saved with new values
2. ✅ `update_base_balance_on_change` (`post_save`, skips if `created`) fires
3. ✅ Signal detects balance-affecting change (or runs unconditionally if `update_fields` wasn't specified)
4. ✅ Base balance recalculated via `calculate_base_balance()`
5. ✅ AccountBalance updated (`update_fields=["base_balance"]`)

**Result**: Balance automatically reflects household changes.

### Order Creation Workflow

**Trigger**: Participant/staff submits an order

**Automatic Steps**:
1. ✅ `Order.save()` generates `order_number` on first save (`_ensure_order_number()` — a **model method override, not a signal**)
2. ✅ Order saved to database
3. ✅ Vouchers marked as consumed via `apply_vouchers_to_order()` / `consume_voucher()` (explicit application-layer calls in `apps/pantry/utils/voucher_utils.py`, not signal-driven)
4. ✅ Account balance reflects consumption (vouchers moved to `state="consumed"`)

**Result**: Order processed with an order-number and voucher-consumption trail.

> Note: no confirmation email is dispatched from a signal (or from anywhere) specifically on order creation — the previous "confirmation email sent" step was not found anywhere in `apps/orders`.

## Signal Configuration

### apps/account/apps.py
```python
class AccountConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.account'

    def ready(self):
        """Import signals when app is ready."""
        import apps.account.signals  # noqa
```

### apps/pantry/apps.py
```python
class PantryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.pantry'
    label = 'pantry'

    def ready(self):
        import apps.pantry.signals  # noqa: F401
```

### apps/lifeskills/apps.py
```python
class LifeskillsConfig(AppConfig):
    ...
    def ready(self):
        """Import signals when app is ready."""
        import apps.lifeskills.signals  # noqa: F401
```

### apps/log/apps.py
```python
class LogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.log'
    label = 'log'

    def ready(self):
        import apps.log.signals  # noqa
```

### core/apps.py
```python
class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        """Import signals when app is ready."""
        import core.signals
```

### apps/voucher/apps.py — ⚠️ does NOT wire up signals
```python
class VoucherConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.voucher'
    label = 'voucher'
```
As noted above, `apps/voucher/apps.py` has no `ready()` method at all. `apps/voucher/signals.py` exists and defines four `@receiver`-decorated functions, but since nothing imports that module, none of them are connected to Django's signal dispatcher. This is very likely unintentional — every other app with a `signals.py` imports it from `ready()`.

## Utility Functions

### Setup Account and Vouchers
**File**: `apps/pantry/utils/voucher_utils.py`

```python
def setup_account_and_vouchers(
    participant, initial_vouchers=2, voucher_type="grocery"
) -> None:
    """
    Ensure a participant has an AccountBalance with calculated base balance
    and initial vouchers. Safe to call multiple times; will not overwrite
    existing accounts.
    """
    if hasattr(participant, "accountbalance"):
        return  # already set up — idempotent no-op

    base_balance = calculate_base_balance(participant)
    account = AccountBalance.objects.create(
        participant=participant,
        base_balance=base_balance
    )

    vouchers = [
        Voucher(account=account, voucher_type=voucher_type, active=True, state="applied")
        for _ in range(initial_vouchers)
    ]
    Voucher.objects.bulk_create(vouchers)
```
Note this creates **2** vouchers with `state="applied"` by default — not a single `state='pending'` voucher as previously documented here, and it does not gate voucher creation on `VoucherSetting.objects.filter(active=True).exists()`.

### Calculate Base Balance
**File**: `apps/account/utils/balance_utils.py`

```python
def calculate_base_balance(participant) -> Decimal:
    """
    Calculate the base balance for a participant based on the active
    VoucherSetting.
    """
    if not participant:
        return Decimal(0)

    setting = VoucherSetting.objects.filter(active=True).first()
    if not setting:
        return Decimal(0)

    adults = getattr(participant, "adults", 0)
    children = getattr(participant, "children", 0)
    diaper_count = getattr(participant, "diaper_count", 0)

    return (
        Decimal(adults) * Decimal(setting.adult_amount) +
        Decimal(children) * Decimal(setting.child_amount) +
        Decimal(diaper_count) * Decimal(setting.infant_modifier)
    )
```
Differences from the previously documented version:
- Reads `infant_modifier` for `diaper_count` too (three factors, not two)
- Returns `Decimal(0)` — **not** `Decimal('20.00')` — when there's no active `VoucherSetting`
- **No minimum floor** of $20; a participant with `adults=0, children=0` gets a `$0` base balance
- `adult_amount` (default `20`) / `child_amount` (default `12.5`) are configurable per-deployment via the `VoucherSetting` model, not hard-coded constants

## Testing Signals

Actual tests use **pytest** (not `django.test.TestCase`) with fixtures, e.g. `apps/account/tests/test_account_balance.py` and `apps/account/tests/test_account_setup.py`. A `VoucherSetting` fixture is required for a non-zero base balance, since `calculate_base_balance()` returns `Decimal(0)` when no active `VoucherSetting` exists.

### Test Signal Firing
```python
import pytest
from apps.account.models import Participant, AccountBalance
from apps.voucher.models import VoucherSetting

@pytest.fixture
def voucher_setting():
    return VoucherSetting.objects.create(active=True, adult_amount=20, child_amount=12.5)

@pytest.mark.django_db
def test_account_created_automatically(voucher_setting):
    """AccountBalance created when participant created (initialize_participant signal)."""
    participant = Participant.objects.create(
        name='Test User', email='test@example.com', adults=2, children=1
    )

    account = AccountBalance.objects.get(participant=participant)
    expected_balance = (2 * voucher_setting.adult_amount) + (1 * voucher_setting.child_amount)
    assert account.base_balance == expected_balance
```

### Test Balance Recalculation
```python
@pytest.mark.django_db
def test_balance_updates_on_household_change(voucher_setting):
    """Base balance updates when household size changes (update_base_balance_on_change signal)."""
    participant = Participant.objects.create(
        name='Test User', email='test@example.com', adults=1, children=0
    )
    account = AccountBalance.objects.get(participant=participant)
    initial_balance = account.base_balance

    participant.children = 1
    participant.save()  # update_fields not passed -> recalculation always runs

    account.refresh_from_db()
    assert account.base_balance > initial_balance
```

## Disabling Signals (Testing)

### Temporarily Disable
```python
from django.db.models.signals import post_save
from apps.account.models import Participant
from apps.account.signals import initialize_participant

# Disconnect signal
post_save.disconnect(initialize_participant, sender=Participant)

# ... test code that shouldn't trigger signal ...

# Reconnect signal
post_save.connect(initialize_participant, sender=Participant)
```
Remember: `Participant` `post_save` has **five** receivers across two files (`apps/account/signals.py` and `apps/pantry/signals.py`). Disconnecting `initialize_participant` alone does not stop `ensure_account_and_vouchers` / `init_account_and_vouchers` in `apps/pantry/signals.py` from also creating the account/vouchers — disconnect all relevant receivers if a test needs signals fully suppressed.

There is no `SIGNAL_ENABLED` Django setting anywhere in this codebase — signals cannot be globally toggled via `override_settings`. The `@override_settings(SIGNAL_ENABLED=False)` pattern previously shown here does not do anything and has been removed.

## Best Practices

### Signal Design
✅ **Do**:
- Keep signals lightweight
- Use async tasks for heavy work
- Check `created` flag in post_save
- Use `update_fields` parameter
- Log signal actions

❌ **Don't**:
- Call `save()` in pre_save (infinite loop!)
- Do expensive operations in signals
- Ignore `created` flag
- Modify unrelated models excessively
- Hide business logic in signals

### Performance
- Use `select_related()` in signal queries
- Batch database operations
- Use `update_fields` to skip signals
- Consider async tasks for emails

### Debugging
```python
import logging
logger = logging.getLogger(__name__)

@receiver(post_save, sender=Participant)
def initialize_participant(instance, created, **kwargs):
    if created:
        logger.info(f"Signal fired for new participant: {instance.id}")
        # ... signal logic ...
```

## Benefits

### For Administrators
- ✅ Automatic account setup
- ✅ No manual voucher creation
- ✅ Consistent data state
- ✅ Reduced manual work

### For Developers
- ✅ Centralized business logic
- ✅ Automatic data integrity
- ✅ Reduced boilerplate
- ✅ Clear event flow

### For System
- ✅ Data consistency
- ✅ Automatic calculations
- ✅ Reduced errors
- ✅ Audit trail

## Monitoring

### Signal Performance
```python
import time
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Participant)
def initialize_participant(instance, created, **kwargs):
    if not created:
        return
    
    start = time.time()
    # ... signal logic ...
    duration = time.time() - start
    
    if duration > 1.0:  # Warn if slow
        logger.warning(f"Slow signal: {duration:.2f}s for participant {instance.id}")
```

## Future Enhancements

> Note: Celery-based async dispatch from signals is already in production use (`initialize_participant` schedules `send_new_user_onboarding_email.delay()` via `transaction.on_commit`; `handle_program_pause` dispatches `update_voucher_flag_task.delay()` / `deactivate_expired_pause_vouchers.apply_async()`), so it's listed here as a pattern to extend further, not a greenfield idea.

- Extend async dispatch to more signal handlers where DB-bound work is currently synchronous (e.g. `create_staff_user_profile_and_onboarding` sends its onboarding email synchronously via `.delay()` call made inline rather than via `transaction.on_commit`)
- Wire up `apps/voucher/signals.py` in `VoucherConfig.ready()` (currently dead code — see [Voucher Signals](#2-voucher-signals))
- Consolidate the duplicate `Participant` `post_save` account/voucher setup logic in `apps/account/signals.py` and `apps/pantry/signals.py` into a single receiver
- Signal dependency tracking
- Signal execution order control
- Conditional signal firing
- Signal performance monitoring
- Signal replay/audit system
