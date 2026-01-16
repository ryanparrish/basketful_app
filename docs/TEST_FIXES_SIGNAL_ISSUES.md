# Test Fixes - Signal and Factory Issues

## Summary
Fixed critical issues with Django signals and Factory Boy that were causing test failures after adding `skip_postgeneration_save = True` to factories.

## Issues Fixed

### 1. Participant Signal Not Persisting User Link
**File**: [apps/account/signals.py](apps/account/signals.py#L31-L62)

**Problem**: The `initialize_participant` signal was creating a user and setting `instance.user = user`, but never saving the instance to persist the relationship to the database.

**Solution**: Added `instance.save(update_fields=['user'])` after linking the user:

```python
elif create_user_flag is True:
    user = create_participant_user(
        first_name=instance.name,
        email=instance.email,
        participant_name=instance.name,
    )
    instance.user = user
    instance.save(update_fields=['user'])  # ADDED THIS LINE
```

**Impact**: Tests that check `participant.user` now correctly see the linked user after participant creation.

### 2. Recursive Signal Triggering AccountBalance.DoesNotExist
**File**: [apps/account/signals.py](apps/account/signals.py#L15-L27)

**Problem**: When `initialize_participant` calls `instance.save(update_fields=['user'])`, it triggers another `post_save` signal, which then triggers `update_base_balance_on_change`. This signal tries to fetch the `AccountBalance`, but it doesn't exist yet because the ParticipantFactory's post-generation hook hasn't run.

**Solution**: Modified `update_base_balance_on_change` to skip execution when `update_fields` is specified and doesn't include balance-affecting fields:

```python
@receiver(post_save, sender=Participant)
def update_base_balance_on_change(instance, created, **kwargs):
    """
    Update AccountBalance.base_balance whenever relevant fields change.
    New participants are ignored (handled by a different signal).
    """
    if created:
        return  # skip new participants
    
    # Skip if update_fields is specified and doesn't include balance-affecting fields
    update_fields = kwargs.get('update_fields')
    if update_fields is not None:
        balance_fields = {'adults', 'children', 'diaper_count'}
        if not balance_fields.intersection(set(update_fields)):
            return  # skip if no balance-affecting fields were updated

    account_balance = AccountBalance.objects.get(participant=instance)
    account_balance.base_balance = calculate_base_balance(instance)
    account_balance.save(update_fields=["base_balance"])
```

**Impact**: Prevents recursive signal errors when saving with `update_fields` that don't affect balance calculations.

### 3. Factory Boy `create_user` Flag Not Working with `skip_postgeneration_save`
**Files**: [apps/account/tests/test_account_setup.py](apps/account/tests/test_account_setup.py#L222-L235)

**Problem**: When using `ParticipantFactory(create_user=True)` with `skip_postgeneration_save = True`, the `create_user` attribute wasn't being set before the initial save, so the signal couldn't see it.

**Solution**: Changed tests to use `.build()` instead of direct factory creation, manually set the attribute, then save:

```python
# Before
participant = ParticipantFactory(create_user=True)

# After
participant = ParticipantFactory.build()
participant.create_user = True
participant.save()
```

**Impact**: Tests can now properly test the `initialize_participant` signal with the `create_user` flag.

## Test Results

**Before Fixes**: 3 tests failing in TestUserOnboardingSignals
**After Fixes**: All 3 tests passing

```
apps/account/tests/test_account_setup.py::TestUserOnboardingSignals::test_initialize_participant_creates_user_and_profile PASSED
apps/account/tests/test_account_setup.py::TestUserOnboardingSignals::test_initialize_participant_triggers_onboarding_email PASSED
apps/account/tests/test_account_setup.py::TestUserOnboardingSignals::test_create_staff_user_triggers_onboarding PASSED
```

## Overall Progress

**Current Status**: 101 tests passing, 10 tests failing, 1 skipped

**Remaining Issues**:
- 3 email task tests (AttributeError/ValueError)
- 1 hygiene rules test (validation not raising)
- 2 admin tests (IntegrityError/Celery)
- 1 voucher logging test (assertion text)
- 1 voucher utils test (Celery)
- 2 combined order tests (unique constraint)

## Lessons Learned

1. **Factory Boy `skip_postgeneration_save`**: While it removes deprecation warnings, it can break tests that rely on signals being triggered after all attributes are set.

2. **Django Signals and Recursive Triggers**: When a signal calls `.save()` on the instance, be careful to use `update_fields` to prevent infinite recursion or triggering unrelated signals.

3. **Testing Signal Behavior**: Tests that check signal behavior need to ensure all required data (like AccountBalance) exists before the signal can successfully execute.

4. **Dynamic Attributes**: Factory Boy parameters passed as kwargs become dynamic attributes, but their timing relative to model save/signals can be tricky. Using `.build()` + manual save gives more control.
