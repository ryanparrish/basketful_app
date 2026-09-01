# Logging & Audit System

> Last updated: 2026-07-13

## Overview
Comprehensive audit logging system that tracks all significant events, changes, and actions throughout the Basketful application. Provides accountability, debugging capabilities, and compliance support. All log models live in `apps/log/models.py` (except `FailedOrderAttempt`, which lives in `apps/orders/models.py` — see `docs/FAILURE_ANALYTICS_GUIDE.md`).

Every log model here is also exposed read-only via the API (`apps/log/api/`, mounted under `/api/v1/`) and browsable in the React-Admin frontend (`frontend/src/resources/logs/`), in addition to the Django admin.

## Log Types

### 1. Email Logs
Track all emails sent by the system.

**Model**: `EmailLog`

**Fields**:
- `user` — FK to the recipient `User` (there is no separate `participant` FK; the recipient's participant is reached via `user.participant`)
- `email_type` — FK to `EmailType`
- `subject` — the rendered subject at send time
- `status` — `sent` or `failed`
- `error_message` — populated when `status='failed'`
- `sent_at` — auto-set on creation
- `message_id` — the Mailgun message ID returned by Anymail (blank for local/dev sends)
- `delivery_status` — `unknown` / `delivered` / `bounced` / `complained` / `unsubscribed` / `failed`, polled from the Mailgun Events API by a Celery task (`sync_mailgun_delivery_status` in `apps/log/tasks/logs.py`) — see `docs/MAILGUN_DELIVERY_INTELLIGENCE.md` for how this fits into the wider delivery-tracking roadmap
- `delivery_checked_at` — when delivery status was last polled
- `retry_count` — how many times a `failed` send has been re-dispatched by the dead-letter-queue task (`retry_failed_emails`)
- `is_test` — true for test sends from the email design studio; excluded from the dedup guard and DLQ retries

**Location**: Admin → Log → Email Logs (also `/api/v1/email-logs/`, staff only)

### 2. Order Validation Logs
Records validation **failures** and staff bypass actions — not a full state-machine of every order's validation lifecycle. There is no `validation_status` field; entries only exist for problems.

**Model**: `OrderValidationLog`

**Fields** (inherited from the shared abstract `BaseLog`, plus `product` and `validated_at`):
- `participant`, `user`, `order` — nullable FKs for context
- `product` — nullable FK to `pantry.Product` (set when a category/product limit violation triggered the entry)
- `message` — the error or warning text
- `log_type` — `INFO` / `WARNING` / `ERROR` (no `pending`/`validated`/`failed` enum — those never existed)
- `created_at`, `validated_at` — both auto-set on creation

**When entries are created** (all direct `.objects.create()` calls, not the `log_model()` helper below):
- `Order.clean()` (`apps/orders/models.py`) — balance/hygiene/Go Fresh/category-limit/voucher validation failures, one row per error message
- `CategoryLimitValidator.validate_category_limits()` (`apps/pantry/models.py`) — category/subcategory limit violations
- Staff bypass paths (`OrderViewSet.confirm`, `perform_update`, `bulk_update_status` in `apps/orders/api/views.py`, and `Order._consume_vouchers()`) — `WARNING`-level audit entries when a staff member with `can_bypass_order_transitions` overrides the balance check or waives voucher consumption (charitable bypass)

**Location**: Admin → Log → Order Validation Logs — registered with a **bare `admin.site.register(OrderValidationLog)`**, i.e. the default Django admin with no custom `list_display`, filters, search, or read-only enforcement (unlike the other log admins in this app, which are all locked down). Also readable via two API routes: `/api/v1/validation-logs/` (`apps/orders/api/`, filtered by `order`) and `/api/v1/order-validation-logs/` (`apps/log/api/`, filtered by `participant`/`order`/`product`/`log_type`) — both read-only, staff only.

### 3. Voucher Logs
Track voucher lifecycle and state changes.

**Inline**: `VoucherLogInline` (appears in Voucher admin)

**Events Logged**:
- Voucher creation and application (`apps/voucher/signals.py`, via `log_voucher()`)
- Voucher amount calculations, balance before/after, remaining amount
- Program pause multiplier context (via the `voucher`/`order` relations)

### 4. User Login Logs
Track authentication activity via Django's built-in auth signals.

**Model**: `UserLoginLog`

**Fields**: `user` (nullable — null for failed attempts against an unknown username), `username_attempted`, `action` (`login` / `logout` / `failed_login`), `ip_address`, `user_agent`, `timestamp`, `participant` (nullable).

**How it's populated**: `apps/log/signals.py` connects to Django's `user_logged_in`, `user_logged_out`, and `user_login_failed` signals — entries are created automatically, not by application code.

**Location**: Admin → Log → User Login Logs (read-only, no add/delete). Also `/api/v1/login-logs/`, with a `failed_logins` filter action.

### 5. Grace Allowance Logs
Intended to record when a participant proceeds with an order that exceeds their balance by an amount within the configured "grace" tolerance (`ProgramSettings.grace_enabled`/`grace_amount`/`grace_message`, used by the `validate_cart` action in `apps/orders/api/views.py` to flag `grace_allowed` violations).

**Model**: `GraceAllowanceLog` — `participant`, `order` (nullable), `amount_over`, `grace_message`, `proceeded`, `created_at`.

**Current state**: the model, admin (`GraceAllowanceLogAdmin`), API (`/api/v1/grace-allowance-logs/`), React-Admin resource, and even a `post_save` notification signal (`core/signals.py::notify_admin_grace_usage`, which writes a `LogEntry` for every staff user when `proceeded=True`) are all built — but **nothing in the codebase currently calls `GraceAllowanceLog.objects.create(...)`**. `validate_cart` computes `grace_allowed` and returns it in the response; no order-confirmation code path persists a `GraceAllowanceLog` row yet. Treat this as a wired-but-not-yet-populated feature rather than a working audit trail.

### 6. System Logs (via Python logging)
Application-level logging for debugging, using standard `logging.getLogger(__name__)` per module (so logger names follow the module path, e.g. `apps.orders.models`, `apps.orders.utils.order_utils`, `apps.pantry.models`) rather than one logger per app.

## Logging Functions

### Generic Log Function

`log_model()` is only used for `VoucherLog` in practice (via the `log_voucher()` wrapper below) — it is not used for `OrderValidationLog`, which is always created directly via `OrderValidationLog.objects.create(...)` (see above). Calling `log_model()` against a model without `balance_before`/`balance_after` fields (like `OrderValidationLog`) would raise a `TypeError`, since those keys are always included in the `create()` call.

```python
from apps.log.logging import log_model, log_voucher

log_voucher(
    message="Voucher state changed: pending → applied",
    log_type="INFO",
    voucher=voucher,
    participant=voucher.account.participant,
    balance_before=100.00,
    balance_after=55.50,
)
```

### Email Logging

```python
from apps.log.models import EmailLog

EmailLog.objects.create(
    email_type=email_type,
    user=user,
    subject=rendered_subject,
    status='sent',
    message_id=message_id,   # Mailgun message ID, or None
)
```

## Admin Features

### Email Logs Admin

**List Display**: id, user, email_type, subject, status, sent_at

**Filters**: status, email_type, sent_at

**Search**: user's email/username, subject

**Features**:
- Read-only (`has_add_permission`, `has_change_permission`, `has_delete_permission` all return `False`)
- No custom color-coding or expandable-error rendering is implemented in the Django admin today — `error_message` is a plain readonly field

### Order Validation Logs Admin

Uses the Django-default admin (`admin.site.register(OrderValidationLog)`) — no custom `list_display`, filters, search, or read-only restriction. All fields are editable and deletable by any staff user with model permissions. If you need the richer, read-only, filterable view of validation logs, use the React-Admin "Order Validation Logs" resource or the `/api/v1/order-validation-logs/` API instead.

## Inline Logs

### VoucherLogInline

Appears in the Voucher admin (`apps/log/inlines.py`) as a read-only inline table:

```python
class VoucherLogInline(admin.TabularInline):
    """Inline admin for VoucherLogs, read-only."""
    model = VoucherLog
    fk_name = 'voucher'
    fields = (
        'participant', 'message', 'log_type',
        'balance_before', 'balance_after', 'created_at',
    )
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True
```

**Usage**:
1. Open any Voucher in admin
2. Scroll to the "Voucher Logs" section
3. View complete history, or follow the change link to the full log entry

## Audit Trail Features

### Immutable Logs
- `EmailLog`, `UserLoginLog`, and `GraceAllowanceLog` are read-only in the Django admin (no add/change/delete)
- `OrderValidationLog` is **not** locked down in the Django admin (see above) — its immutability is enforced only by convention (nothing in the codebase edits existing rows) and by the read-only API/React-Admin views
- Timestamps are auto-generated (`auto_now_add`) on every log model

### Comprehensive Tracking
- **Who**: `user`/`participant` FKs where applicable
- **What**: `message`/`error_summary` text
- **When**: `created_at`/`sent_at`/`timestamp`
- **Where**: `order`/`voucher`/`product` FKs
- **Result**: `status`/`log_type`

### Relationship Tracking
Logs maintain relationships to Users, Participants, Orders, Vouchers, Products, and Email types — the exact set of relations differs per log model (see field lists above).

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
    log_type='ERROR',
    created_at__gte=last_week
)
```

### Find User Activity
```python
user_actions = UserLoginLog.objects.filter(
    user=user,
    timestamp__date=today
)
```

## Reporting

### Email Delivery Report
```python
from django.db.models import Count, Q

email_stats = EmailLog.objects.values('email_type__display_name').annotate(
    total=Count('id'),
    sent=Count('id', filter=Q(status='sent')),
    failed=Count('id', filter=Q(status='failed'))
)
```

### Order Validation Report
```python
validation_stats = OrderValidationLog.objects.filter(
    created_at__date=today
).aggregate(
    total=Count('id'),
    errors=Count('id', filter=Q(log_type='ERROR')),
    warnings=Count('id', filter=Q(log_type='WARNING')),
)
```

## Technical Implementation

### Models

**apps/log/models.py** (abbreviated — see full model definitions for all fields):
```python
class EmailLog(models.Model):
    STATUS_CHOICES = [("sent", "Sent"), ("failed", "Failed")]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    email_type = models.ForeignKey(EmailType, on_delete=models.PROTECT, related_name='logs')
    subject = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="sent")
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    message_id = models.CharField(max_length=255, blank=True, null=True)
    delivery_status = models.CharField(max_length=20, default="unknown")
    delivery_checked_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    is_test = models.BooleanField(default=False)
```

### Inlines

**apps/log/inlines.py** — see `VoucherLogInline` above.

### Logging Utility

**apps/log/logging.py**:
```python
def log_model(
    model: Type[Model],
    message: str,
    log_type: str = "INFO",
    order: Optional[Order] = None,
    voucher: Optional[Voucher] = None,
    participant: Optional[Participant] = None,
    balance_before: Optional[float] = None,
    balance_after: Optional[float] = None,
) -> Model:
    """Generic logging function for audit models (used for VoucherLog only in practice)."""
    kwargs = {
        "message": message,
        "log_type": log_type,
        "participant": participant,
        "balance_before": balance_before,
        "balance_after": balance_after,
    }
    if hasattr(model, "order"):
        kwargs["order"] = order
    if hasattr(model, "voucher"):
        kwargs["voucher"] = voucher
    return model.objects.create(**kwargs)


def log_voucher(*args, **kwargs):
    return log_model(VoucherLog, *args, **kwargs)
```

## Security Considerations

### Read-Only Access
- `EmailLog`, `UserLoginLog`, `GraceAllowanceLog` admins block add/change/delete
- `OrderValidationLog`'s Django admin does **not** block anything (see above) — rely on model-level Django permissions if you need to restrict who can edit it there

### Sensitive Data
- Passwords never logged
- Cart contents in `FailedOrderAttempt` store product IDs/names/prices, not participant PII beyond what's already on the participant record

### Access Control
- All log API endpoints require `IsAuthenticated` + `IsStaffUser`
- Django admin permissions enforced for Django-admin access

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
- ✅ Audit trail for emails, logins, and order validation failures
- ✅ Immutable records where admin permissions are locked down
- ✅ User attribution
- ✅ Timestamp accuracy

## Future Enhancements

- Lock down the `OrderValidationLog` Django admin the same way as the other log models
- Wire up `GraceAllowanceLog` creation in the order-confirmation flow (model/admin/API/notification signal already exist)
- Log retention policies for models other than `FailedOrderAttempt` (which already has `cleanup_failed_attempts`)
- Log export to external systems
- Real-time alerting
- Log analytics dashboard
- Anomaly detection
