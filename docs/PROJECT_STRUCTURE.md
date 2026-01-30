# 🧭 Project Structure — Basketful

> Last updated: January 2026

This document outlines the folder and file hierarchy for **Basketful**,  
a Django-based food pantry and voucher management application.

Use this as a quick reference for navigating the codebase and understanding where key logic lives —  
such as models, views, utils, and orchestration helpers.

---

## 📂 Folder Tree

```
basketful_app/
├── manage.py                    # Django management script
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Container configuration
├── pytest.ini                   # Pytest configuration
├── db.sqlite3                   # Development database
│
├── apps/                        # Django applications
│   ├── account/                 # Account & balance management
│   │   ├── admin.py
│   │   ├── models.py            # AccountBalance model
│   │   ├── signals.py
│   │   ├── utils/
│   │   │   └── balance_utils.py # Balance calculation functions
│   │   ├── tasks/               # Celery tasks
│   │   └── tests/
│   │
│   ├── lifeskills/              # Life skills program
│   │   ├── models.py            # ProgramPause model
│   │   ├── queryset.py
│   │   ├── signals.py
│   │   └── tests/
│   │
│   ├── log/                     # Logging & validation
│   │   ├── models.py            # OrderValidationLog model
│   │   ├── logging.py
│   │   └── templates/
│   │
│   ├── orders/                  # Order management
│   │   ├── models.py            # Order, OrderItem, OrderVoucher
│   │   ├── forms.py
│   │   ├── utils/
│   │   └── tests/
│   │
│   ├── pantry/                  # Product catalog & ordering UI
│   │   ├── admin.py
│   │   ├── models.py            # Category, Product, Tag, GoFreshSettings
│   │   ├── forms.py
│   │   ├── middleware.py
│   │   ├── validators.py
│   │   ├── static/
│   │   ├── templates/
│   │   │   └── food_orders/
│   │   │       └── create_order.html  # Mobile ordering UI
│   │   └── tests/
│   │
│   └── voucher/                 # Voucher system
│       ├── models.py            # Voucher, VoucherSetting models
│       └── tests/
│
├── core/                        # Project configuration
│   ├── settings.py              # Django settings
│   ├── urls.py                  # URL routing
│   ├── celery.py                # Celery configuration
│   ├── middleware.py
│   └── templates/               # Base templates
│
├── docs/                        # Documentation
│   ├── INDEX.md                 # Documentation index
│   ├── ARCHITECTURE.md          # System architecture
│   └── diagrams/                # Mermaid source files
│
├── scripts/                     # Utility scripts
│
└── coverage/                    # Test coverage reports
```

---

## 🗂️ Key Files by Concern

### Balance Calculations
- `apps/account/models.py` — `AccountBalance` model with balance properties
- `apps/account/utils/balance_utils.py` — `calculate_available_balance()`, `calculate_hygiene_balance()`, etc.
- `apps/pantry/models.py` — `GoFreshSettings` singleton for Go Fresh budgets

### Order Processing
- `apps/orders/models.py` — `Order`, `OrderItem`, `OrderVoucher` models
- `apps/orders/models.py::Order.clean()` — Balance validation
- `apps/orders/models.py::Order.confirm_order()` — Voucher consumption

### Voucher Management
- `apps/voucher/models.py` — `Voucher`, `VoucherSetting` models
- `apps/voucher/models.py::Voucher.state` — Voucher lifecycle states

### Mobile UI
- `apps/pantry/templates/food_orders/create_order.html` — Main ordering interface
- `apps/pantry/static/` — JavaScript and CSS assets

### Signals & Automation
- `apps/account/signals.py` — Account creation triggers
- `apps/pantry/signals.py` — Category/product signals
- `apps/orders/signals.py` — Order confirmation signals

---

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — System architecture overview
- [TESTING.md](TESTING.md) — Test organization and running tests
