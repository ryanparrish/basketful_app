# 🧭 Project Structure — Basketful

> Last updated: 2026-07-13

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
├── Dockerfile                   # Container configuration (Django app)
├── pytest.ini                   # Pytest configuration
├── render.yaml                  # Render.com deployment config
├── docker-compose.frontend-admin.yml         # Local admin frontend container
├── docker-compose.frontend-participant.yml   # Local participant frontend container
├── docker-compose.prod.images.yml            # Prod-style multi-image compose
├── package.json / package-lock.json          # Root Jest config
├── jest.config.js / jest.setup.js            # Jest for apps/*/static/js/*.test.js
├── codecov.yml                   # Coverage reporting config
│
├── apps/                        # Django applications
│   ├── account/                 # Participants & account balances
│   │   ├── admin.py
│   │   ├── models.py            # UserProfile, Participant, AccountBalance,
│   │   │                        # GoFreshSettings, HygieneSettings, BulkCreateBatch
│   │   ├── signals.py
│   │   ├── utils/
│   │   │   └── balance_utils.py # Balance calculation functions
│   │   ├── tasks/                # Celery tasks (email, order window)
│   │   └── tests/
│   │
│   ├── api/                      # Shared DRF plumbing (no models)
│   │   ├── pagination.py         # StandardResultsSetPagination (react-admin Content-Range)
│   │   ├── permissions.py        # IsAdminOrReadOnly, IsStaffUser, IsLifeskillsCoach, etc.
│   │   └── urls.py               # /api/v1/ router + JWT auth endpoints
│   │
│   ├── lifeskills/               # Life skills program
│   │   ├── models.py             # Program, ProgramPause, LifeskillsCoach
│   │   ├── queryset.py
│   │   ├── signals.py
│   │   └── tests/
│   │
│   ├── log/                      # Email delivery & audit logging
│   │   ├── models.py             # EmailType, EmailLog, BaseLog, VoucherLog,
│   │   │                         # OrderValidationLog, UserLoginLog, GraceAllowanceLog
│   │   ├── logging.py
│   │   └── templates/
│   │
│   ├── orders/                   # Order management & warehouse fulfillment
│   │   ├── models.py             # FailedOrderAttempt, Order, OrderItem, CombinedOrder,
│   │   │                         # PackingSplitRule, PackingList, WarehouseInventoryList
│   │   ├── forms.py
│   │   ├── utils/
│   │   └── tests/
│   │
│   ├── pantry/                   # Product catalog & ordering support
│   │   ├── admin.py
│   │   ├── models.py             # Category, Subcategory, Tag, Product, ProductLimit,
│   │   │                         # OrderPacker, LowInventoryAlertSettings
│   │   ├── forms.py
│   │   ├── middleware.py
│   │   ├── validators.py
│   │   ├── static/js/            # cart.js, filter.js + Jest specs (cart.test.js, etc.)
│   │   ├── templates/
│   │   │   └── food_orders/      # participant_dashboard.html, review_order.html, etc.
│   │   └── tests/
│   │
│   └── voucher/                  # Voucher system
│       ├── models.py             # VoucherSetting, Voucher, OrderVoucher
│       └── tests/
│
├── core/                          # Project configuration
│   ├── settings.py                # Django settings (DATABASE_URL required, no sqlite fallback)
│   ├── urls.py                    # URL routing
│   ├── celery.py                  # Celery configuration + beat schedule
│   ├── middleware.py
│   └── templates/
│       ├── base.html              # Base template
│       └── pantry/
│           └── create_order.html  # Mobile ordering UI (rendered by apps/pantry/views.py)
│
├── frontend/                      # Admin React app (Vite + TypeScript, Playwright e2e)
├── participant-frontend/          # Participant-facing React app (Vite + TypeScript)
├── nginx/                         # nginx.conf + conf.d/basketful.conf
├── locale/                        # Translations (es)
│
├── docs/                          # Documentation
│   ├── INDEX.md                   # Documentation index
│   ├── ARCHITECTURE.md            # System architecture
│   └── diagrams/                  # Mermaid source files (.mmd) + rendering README
│
├── scripts/                       # Deploy, debug, and diagnostic scripts
│                                   # (deploy.sh, render_diagrams.sh, run-mutations.sh,
│                                   #  debug_product_*.py, demo_order_window.py, etc.)
│
└── .github/                       # CI workflows, Dependabot, issue templates, prompts
```

---

## 🗂️ Key Files by Concern

### Balance Calculations
- `apps/account/models.py` — `AccountBalance` model; `full_balance`/`available_balance`/`hygiene_balance`/`go_fresh_balance` are computed properties
- `apps/account/utils/balance_utils.py` — `calculate_full_balance()`, `calculate_available_balance()`, `calculate_hygiene_balance()`, `calculate_go_fresh_balance()`
- `apps/account/models.py` — `GoFreshSettings`, `HygieneSettings` singletons (both live in `account`, not `pantry`)

### Order Processing
- `apps/orders/models.py` — `Order`, `OrderItem`, `CombinedOrder`, `PackingList`, `WarehouseInventoryList` models
- `apps/orders/models.py::Order.clean()` — Balance and category-limit validation
- `apps/orders/models.py::Order.confirm()` and `Order._consume_vouchers()` — Confirmation and voucher consumption

### Voucher Management
- `apps/voucher/models.py` — `Voucher`, `VoucherSetting`, and `OrderVoucher` (the order↔voucher join model lives in `voucher`, not `orders`)
- `apps/voucher/models.py::Voucher.state` — Voucher lifecycle states (pending → applied → consumed/expired)

### API Layer
- `apps/api/urls.py` — `/api/v1/` router and JWT auth endpoints; includes each app's `apps/<app>/api/urls.py`
- `apps/api/pagination.py` — `StandardResultsSetPagination` (react-admin `Content-Range` header)
- `apps/api/permissions.py` — Shared DRF permission classes (`IsAdminOrReadOnly`, `IsStaffUser`, `IsLifeskillsCoach`, `IsCoachOrStaff`, `IsOwnerOrAdmin`, `CanBypassOrderTransitions`, etc.)

### Ordering UI
- `core/templates/pantry/create_order.html` — Main ordering interface, rendered by `apps/pantry/views.py::product_view`
- `apps/pantry/templates/food_orders/` — Participant dashboard, review, and order-success templates
- `apps/pantry/static/js/` — Cart/filter JavaScript, with Jest specs run via the root `jest.config.js`

### Signals & Automation
- `apps/account/signals.py` — Account creation triggers
- `apps/pantry/signals.py` — Category/product signals
- Order confirmation and voucher consumption are handled directly by `Order.confirm()` / `Order._consume_vouchers()` (`apps/orders/models.py`) — there is no `apps/orders/signals.py`
- `core/settings.py::CELERY_BEAT_SCHEDULE` — Periodic tasks (weekly combined orders, pause-flag cleanup, Mailgun delivery sync, order-window notifications, email retry, low-inventory check)

---

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — System architecture overview
- [TESTING.md](TESTING.md) — Test organization and running tests
