# Testing

> Last updated: January 2026

This document covers testing practices, commands, and organization for the Basketful project.

## Quick Start

Run the full test suite with coverage:

```bash
source .venv/bin/activate
python -m pytest --cov=apps --cov-report=xml --cov-report=html
```

Quick test run (single file):

```bash
python -m pytest apps/account/tests/test_account_balance.py -v
```

Run tests matching a pattern:

```bash
python -m pytest -k "test_go_fresh" -v
```

## Test Organization

Tests are located in each app's `tests/` directory:

```
apps/
├── account/tests/
│   ├── test_account_balance.py    # Balance calculation tests
│   └── test_signals.py
├── orders/tests/
│   ├── test_order_validation.py   # Order clean() validation
│   ├── test_go_fresh_validation.py
│   └── test_combined_orders.py
├── pantry/tests/
│   ├── test_category_protection.py
│   ├── test_products.py
│   └── test_go_fresh_settings.py
├── voucher/tests/
│   └── test_voucher_lifecycle.py
└── lifeskills/tests/
    └── test_program_pause.py
```

## Test Fixtures

### Factory Boy

The project uses `factory_boy` for test data. Key factories:

```python
from apps.account.tests.factories import AccountBalanceFactory, ParticipantFactory
from apps.voucher.tests.factories import VoucherFactory, VoucherSettingFactory
from apps.orders.tests.factories import OrderFactory, OrderItemFactory
from apps.pantry.tests.factories import CategoryFactory, ProductFactory
```

### VoucherSettingFactory

Many tests require an active `VoucherSetting`. Use an autouse fixture:

```python
@pytest.fixture(autouse=True)
def voucher_setting():
    from apps.voucher.tests.factories import VoucherSettingFactory
    return VoucherSettingFactory(active=True)
```

## Mocking Celery Tasks

When creating users in tests, signals may trigger Celery tasks. Mock them to avoid broker connection errors:

```python
from unittest.mock import patch

@pytest.fixture
def admin_user(db):
    with patch('apps.account.tasks.onboarding.send_new_user_onboarding_email.delay'):
        user = User.objects.create_superuser(...)
        return user
```

## Test Configuration

### pytest.ini

```ini
[pytest]
DJANGO_SETTINGS_MODULE = core.settings
python_files = test_*.py
python_functions = test_*
addopts = -v --tb=short
```

### Environment Variables

Tests use defaults for most settings. Required in CI:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | Django secret key |
| `DOMAIN_NAME` | Test domain (e.g., `test.example.com`) |
| `HASHIDS_SALT` | Salt for hashids |
| `CELERY_TASK_ALWAYS_EAGER` | Set `true` for synchronous tasks |

## Coverage

Coverage reports are generated in `coverage/`:

- `coverage/lcov-report/index.html` — HTML report
- `coverage/lcov.info` — LCOV format for CI tools
- `coverage/clover.xml` — Clover format

View HTML report:

```bash
open coverage/lcov-report/index.html
```

## Common Test Patterns

### Testing Balance Calculations

```python
def test_available_balance_with_two_vouchers(account_balance):
    VoucherFactory(account=account_balance, state="applied", voucher_amnt=50)
    VoucherFactory(account=account_balance, state="applied", voucher_amnt=30)
    
    assert account_balance.available_balance == Decimal("80.00")
```

### Testing Order Validation

```python
def test_order_exceeds_balance(order):
    order.total = Decimal("1000.00")  # Exceeds available
    
    with pytest.raises(ValidationError, match="exceeds available balance"):
        order.clean()
```

## Related Documentation

- [CI.md](CI.md) — CI/CD workflow configuration
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) — Test file locations