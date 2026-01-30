# Logging & Audit System

> Last updated: January 2026

## Overview
Comprehensive audit logging system that tracks all significant events, changes, and actions throughout the Basketful application. Provides accountability, debugging capabilities, and compliance support.

## Log Types

### 1. Email Logs
Track all emails sent by the system.

**Model**: `EmailLog`

**Fields**:
- Email type and template used
- Recipient email address
- Subject and timestamp
- Success/failure status
- Error messages if failed
- Associated user/participant

**Location**: Admin → Log → Email Logs

### 2. Order Validation Logs
Track order validation and voucher application.

**Model**: `OrderValidationLog`

**Fields**:
- Order reference
- Validation status (pending/validated/failed)
- Validation messages
- Vouchers applied
- Balance before/after
- Timestamp and user

**Location**: Admin → Log → Order Validation Logs

### 3. Voucher Logs
Track voucher lifecycle and state changes.

**Inline**: `VoucherLogInline` (appears in Voucher admin)

**Events Logged**:
- Voucher creation
- Status changes (pending → applied → consumed)
- Voucher amount calculations
- Program pause multipliers
- Account associations

### 4. System Logs (via Python logging)
Application-level logging for debugging.

**Loggers**:
- `apps.orders` - Order processing
- `apps.voucher` - Voucher operations
- `apps.account` - Account changes
- `apps.pantry` - Product operations

## Logging Functions

### Generic Log Function

```python
from apps.log.logging import log_model

log_model(
    model=OrderValidationLog,
    message="Order validated successfully",
    log_type="INFO",
    order=order,
    voucher=voucher,
    participant=participant,
    balance_before=100.00,
    balance_after=55.50
)
```

### Email Logging

```python
from apps.log.models import EmailLog

EmailLog.objects.create(
    email_type=email_type,
    recipient=user.email,
    subject=rendered_subject,
    sent_at=timezone.now(),
    status='sent',
    user=user,
    participant=participant
)
```

## Admin Features

### Email Logs Admin

**List Display**:
- Email type
- Recipient
- Subject
- Status (✓/✗)
- Sent timestamp

**Filters**:
- Email type
- Status
- Date sent

**Search**:
- Recipient email
- Subject
- Error messages

**Features**:
- Read-only (audit integrity)
- Color-coded status indicators
- Expandable error messages
- User/participant links

### Order Validation Logs Admin

**List Display**:
- Order reference
- Participant name
- Validation status
- Balance change
- Timestamp

**Filters**:
- Validation status
- Date range

**Features**:
- Drill-down to order details
- Balance before/after comparison
- Voucher application tracking

## Inline Logs

### VoucherLogInline

Appears in Voucher admin as inline table showing:
- Log entries for this voucher
- Chronological order
- Event type and timestamp
- User who made changes

**Usage**:
1. Open any Voucher in admin
2. Scroll to "Voucher Logs" section
3. View complete history

## Audit Trail Features

### Immutable Logs
- All log entries are read-only
- No delete permission in admin
- Timestamp auto-generated
- Cannot be modified after creation

### Comprehensive Tracking
- **Who**: User who performed action
- **What**: Action taken
- **When**: Precise timestamp
- **Where**: Object affected
- **Why**: Context and messages
- **Result**: Success/failure status

### Relationship Tracking
Logs maintain relationships to:
- Users
- Participants
- Orders
- Vouchers
- Email types

## Usage Examples

### Track Order Processing

```python
# Log order validation start
log_model(
    model=OrderValidationLog,
    message="Starting order validation",
    log_type="INFO",
    order=order,
    participant=participant,
    balance_before=account.available_balance
)

# ... validation logic ...

# Log successful validation
log_model(
    model=OrderValidationLog,
    message=f"Order validated: {len(items)} items",
    log_type="SUCCESS",
    order=order,
    participant=participant,
    balance_before=balance_before,
    balance_after=account.available_balance
)
```

### Track Email Sending

```python
try:
    send_mail(...)
    EmailLog.objects.create(
        email_type=email_type,
        recipient=email,
        subject=subject,
        status='sent',
        sent_at=timezone.now()
    )
except Exception as e:
    EmailLog.objects.create(
        email_type=email_type,
        recipient=email,
        subject=subject,
        status='failed',
        error_message=str(e),
        sent_at=timezone.now()
    )
```

### Track Voucher Changes

```python
from apps.log.inlines import VoucherLogInline

# Automatic logging via signals or manual
log_model(
    model=VoucherLog,
    message=f"Voucher state changed: {old_state} → {new_state}",
    log_type="INFO",
    voucher=voucher,
    participant=voucher.account.participant
)
```

## Querying Logs

### Find Failed Emails
```python
failed_emails = EmailLog.objects.filter(
    status='failed',
    sent_at__gte=today
)
```

### Find Validation Errors
```python
failed_validations = OrderValidationLog.objects.filter(
    validation_status='failed',
    created_at__gte=last_week
)
```

### Find User Activity
```python
user_actions = OrderValidationLog.objects.filter(
    user=user,
    created_at__date=today
)
```

## Reporting

### Email Delivery Report
```python
from django.db.models import Count

email_stats = EmailLog.objects.values('email_type__display_name').annotate(
    total=Count('id'),
    sent=Count('id', filter=Q(status='sent')),
    failed=Count('id', filter=Q(status='failed'))
)
```

### Order Processing Report
```python
validation_stats = OrderValidationLog.objects.filter(
    created_at__date=today
).aggregate(
    total=Count('id'),
    successful=Count('id', filter=Q(validation_status='validated')),
    failed=Count('id', filter=Q(validation_status='failed'))
)
```

## Technical Implementation

### Models

**apps/log/models.py**:
```python
class EmailLog(models.Model):
    email_type = models.ForeignKey(EmailType, on_delete=models.CASCADE)
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    sent_at = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=[('sent', 'Sent'), ('failed', 'Failed')]
    )
    error_message = models.TextField(blank=True)
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    participant = models.ForeignKey(
        Participant, null=True, on_delete=models.SET_NULL
    )
```

### Inlines

**apps/log/inlines.py**:
```python
class VoucherLogInline(admin.TabularInline):
    model = VoucherLog
    extra = 0
    readonly_fields = ('created_at', 'log_type', 'message')
    can_delete = False
```

### Logging Utility

**apps/log/logging.py**:
```python
def log_model(
    model: Type[Model],
    message: str,
    log_type: str = "INFO",
    **kwargs
) -> Model:
    """
    Generic logging function for audit models.
    Creates log entry with provided context.
    """
    return model.objects.create(
        message=message,
        log_type=log_type,
        **kwargs
    )
```

## Security Considerations

### Read-Only Access
- Logs cannot be edited after creation
- Admin users cannot delete logs
- Preserves audit integrity

### Sensitive Data
- Passwords never logged
- Personal data minimized
- Error messages sanitized

### Access Control
- Only staff can view logs
- Superusers only for sensitive logs
- Django admin permissions enforced

## Benefits

### For Administrators
- ✅ Track all system activity
- ✅ Investigate issues
- ✅ Audit compliance
- ✅ Monitor email delivery

### For Developers
- ✅ Debug production issues
- ✅ Understand user flows
- ✅ Track down errors
- ✅ Performance analysis

### For Compliance
- ✅ Complete audit trail
- ✅ Immutable records
- ✅ User attribution
- ✅ Timestamp accuracy

## Future Enhancements

- Log retention policies
- Log export to external systems
- Real-time alerting
- Log analytics dashboard
- Anomaly detection
- Log archival system
