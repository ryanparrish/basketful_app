# Signals & Automation System

## Overview
Django signals provide automatic responses to model events, enabling seamless automation throughout Basketful. The system automatically handles account creation, voucher generation, user setup, and more.

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

#### Auto-Create Account Balance
```python
@receiver(post_save, sender=Participant)
def initialize_participant(instance, created, **kwargs):
    """
    When a new participant is created:
    - Create AccountBalance
    - Calculate base balance
    - Create initial vouchers
    - Setup user account (if requested)
    - Send onboarding email
    """
```

**Triggers**: New participant creation

**Actions**:
1. Create `AccountBalance` record
2. Calculate `base_balance` from household size
3. Call `setup_account_and_vouchers()`
4. Create `User` if `create_user=True`
5. Send onboarding email

#### Update Base Balance on Change
```python
@receiver(post_save, sender=Participant)
def update_base_balance_on_change(instance, created, **kwargs):
    """
    When participant household changes:
    - Recalculate base_balance
    - Update AccountBalance
    - Skip if only non-balance fields changed
    """
```

**Triggers**: Participant update

**Watched Fields**:
- `adults`
- `children`
- `diaper_count`

**Actions**:
1. Detect if balance-affecting fields changed
2. Recalculate base balance
3. Update AccountBalance record

### 2. Voucher Signals

**File**: `apps/voucher/signals.py`

#### Voucher State Tracking
```python
@receiver(post_save, sender=Voucher)
def log_voucher_changes(instance, created, **kwargs):
    """
    Track voucher lifecycle:
    - Creation
    - State changes
    - Amount calculations
    """
```

**Triggers**: Voucher creation or update

**Actions**:
- Log voucher creation
- Log state transitions
- Track voucher amounts
- Record program pause multipliers

### 3. Order Signals

**File**: `apps/pantry/signals.py`

#### Order Number Generation
```python
@receiver(pre_save, sender=Order)
def generate_order_number(instance, **kwargs):
    """
    Generate order number on creation:
    Format: ORD-YYYYMMDD-XXXXXX
    """
```

**Triggers**: Order creation

**Actions**:
1. Check if order_number exists
2. Generate format: `ORD-20260117-000123`
3. Assign to order

### 4. User Profile Signals

**File**: `apps/account/signals.py`

#### Auto-Create UserProfile
```python
@receiver(post_save, sender=User)
def create_user_profile(instance, created, **kwargs):
    """
    Create UserProfile for every User:
    - Set must_change_password=True
    - Link to User
    """
```

**Triggers**: User creation

**Actions**:
1. Create `UserProfile` instance
2. Set password change flag
3. Link to user

## Automation Workflows

### New Participant Workflow

**Trigger**: Administrator creates participant

**Automatic Steps**:
1. ✅ Participant saved to database
2. ✅ `post_save` signal fired
3. ✅ AccountBalance created
4. ✅ Base balance calculated (adults × $20 + children × $12.50)
5. ✅ Initial vouchers created
6. ✅ User account created (if requested)
7. ✅ UserProfile created
8. ✅ Onboarding email sent (if user created)
9. ✅ Customer number generated

**Result**: Fully configured participant ready to order!

### Household Change Workflow

**Trigger**: Administrator updates household size

**Automatic Steps**:
1. ✅ Participant saved with new values
2. ✅ `post_save` signal fired
3. ✅ Signal detects balance-affecting change
4. ✅ Base balance recalculated
5. ✅ AccountBalance updated
6. ✅ Available balance adjusted

**Result**: Balance automatically reflects household changes!

### Order Creation Workflow

**Trigger**: Participant submits order

**Automatic Steps**:
1. ✅ Order validated
2. ✅ `pre_save` signal generates order number
3. ✅ Order saved to database
4. ✅ Vouchers marked as consumed
5. ✅ Account balance updated
6. ✅ Confirmation email sent

**Result**: Order processed with full audit trail!

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

### apps/voucher/apps.py
```python
class VoucherConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.voucher'

    def ready(self):
        import apps.voucher.signals  # noqa
```

## Utility Functions

### Setup Account and Vouchers
**File**: `apps/pantry/utils/voucher_utils.py`

```python
def setup_account_and_vouchers(participant):
    """
    Complete account setup:
    1. Get or create AccountBalance
    2. Calculate base balance
    3. Create initial voucher
    4. Apply program pause logic
    """
    account, created = AccountBalance.objects.get_or_create(
        participant=participant,
        defaults={'base_balance': calculate_base_balance(participant)}
    )
    
    voucher_setting = VoucherSetting.objects.filter(active=True).first()
    if voucher_setting:
        Voucher.objects.create(
            account=account,
            voucher_type='grocery',
            state='pending'
        )
    
    return account
```

### Calculate Base Balance
**File**: `apps/account/utils/balance_utils.py`

```python
def calculate_base_balance(participant):
    """
    Calculate base balance from household:
    - Adults: $20 each
    - Children: $12.50 each
    - Minimum: $20
    """
    voucher_setting = VoucherSetting.objects.filter(active=True).first()
    if not voucher_setting:
        return Decimal('20.00')
    
    adult_amount = voucher_setting.adult_amount
    child_amount = voucher_setting.child_amount
    
    base = (
        participant.adults * adult_amount +
        participant.children * child_amount
    )
    
    return max(base, Decimal('20.00'))
```

## Testing Signals

### Test Signal Firing
```python
from django.test import TestCase
from apps.account.models import Participant, AccountBalance

class ParticipantSignalTests(TestCase):
    def test_account_created_automatically(self):
        """AccountBalance created when participant created."""
        participant = Participant.objects.create(
            name='Test User',
            email='test@example.com',
            adults=2,
            children=1
        )
        
        # Signal should have created AccountBalance
        self.assertTrue(
            AccountBalance.objects.filter(participant=participant).exists()
        )
        
        account = AccountBalance.objects.get(participant=participant)
        expected_balance = (2 * 20) + (1 * 12.50)  # $52.50
        self.assertEqual(account.base_balance, expected_balance)
```

### Test Balance Recalculation
```python
def test_balance_updates_on_household_change(self):
    """Base balance updates when household size changes."""
    participant = Participant.objects.create(
        name='Test User',
        email='test@example.com',
        adults=1,
        children=0
    )
    
    account = AccountBalance.objects.get(participant=participant)
    initial_balance = account.base_balance  # $20
    
    # Add a child
    participant.children = 1
    participant.save()
    
    account.refresh_from_db()
    # Should now be $20 + $12.50 = $32.50
    self.assertGreater(account.base_balance, initial_balance)
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

### Using Django Test Helpers
```python
from django.test.utils import override_settings

@override_settings(SIGNAL_ENABLED=False)
def test_without_signals(self):
    """Test with signals disabled."""
    # Signals won't fire here
    pass
```

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

- Async signal handlers (Celery)
- Signal dependency tracking
- Signal execution order control
- Conditional signal firing
- Signal performance monitoring
- Signal replay/audit system
