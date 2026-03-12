# Basketful — Claude Context

Food pantry management system for tracking participants, vouchers, orders, and account balances. Built for warehouse staff and program coordinators.

---

## Coding Philosophy

### Money is always `Decimal`. Never float.
Every financial field is `DecimalField`. Every calculation uses `Decimal()`. Floats are forbidden for anything that touches a balance, price, or voucher amount — floating-point rounding errors in financial software directly harm real people.

### Validate in `clean()`. Mutate in a separate step.
Order validation lives in `Order.clean()`. Voucher consumption lives in `Order._consume_vouchers()`. These are intentionally separate. `Order.confirm()` is explicit about this: *"Validation should happen BEFORE this method is called."* Never silently validate and mutate in the same method.

### Protect money with transactions and locks.
All order submission paths use `@transaction.atomic` and `select_for_update()` on `AccountBalance`. This prevents double-spending. Any new code that reads a balance and then writes based on it must follow this pattern.

### Save only what you changed.
Use `save(update_fields=[...])` everywhere. A broad `.save()` on a model that has signal handlers (like `Participant` or `Voucher`) can trigger unintended cascades — balance recalculations, email sends, voucher creation. Be explicit.

### Audit everything financial.
`FailedOrderAttempt`, `OrderValidationLog`, `VoucherLog`, `EmailLog` exist for a reason. When money moves or validation fails, write a record. Logging failures should never suppress the original error — the pattern is `try/except` around log creation, not around the business logic.

### Pure functions for business rules.
Balance calculations live in `apps/account/utils/balance_utils.py`, not on models. Utility functions take explicit arguments and return values. They don't touch the database unless they have to. This makes them testable in isolation and reusable across signals, views, and tasks.

### Singletons enforce global configuration.
`VoucherSetting`, `GoFreshSettings`, and `OrderWindowSettings` all use the singleton pattern — `save()` deactivates all other instances when `active=True`. When adding a new globally-configured feature, follow this pattern. Always guard with `.filter(active=True).first()` and handle the `None` case gracefully.

### Signals are declarative automation, not hidden logic.
Django signals handle the participant → account → voucher → email chain automatically. This is intentional — staff shouldn't have to manually trigger these steps. But signal handlers must be defensive: check `created`, check `update_fields`, never assume the trigger is what you think it is. Document what each signal does and when it fires.

### Defend against missing data with `getattr`.
`getattr(obj, 'field', default)` is used throughout, especially when traversing FK relationships that might be null. Never assume a participant has an account, an account has a balance, or a voucher has a non-null amount. The system has real data from real people — partial records exist.

### Log at the module level, not inline.
Every module that does meaningful work has `logger = logging.getLogger(__name__)` at the top. Use `logger.info` for business events, `logger.error` for failures, never `print`. This makes production debugging tractable.

### Test with factories, not fixtures.
`factory_boy` is the source of truth for test data. Fixtures go stale; factories reflect the current schema. Tests that need a `VoucherSetting` must create one explicitly — don't rely on database state leaking between tests.

### RBAC is enforced at the API layer.
The seven default groups are the expected permission model. New API views should use the shared permission classes from `apps/api/permissions.py` rather than writing inline `request.user.is_staff` checks. Staff-only writes, authenticated reads, object-level owner checks — all already implemented.

### The participant is the center of everything.
`Participant` → `AccountBalance` → `Voucher` → `Order` is the canonical ownership chain. Every model that involves money or shopping flows through this chain. When adding a feature, ask: where does this fit in that chain, and what cascades does it affect?

### Enforce business rules at the model level.
Constraints belong in models, not just views or serializers. Use `clean()` for cross-field validation, `MinValueValidator` on fields, `unique=True` and `unique_together` where data integrity demands it, and `on_delete=PROTECT` when deleting a parent would silently corrupt financial records (e.g., `Order` → `AccountBalance`). A model that can be saved into an invalid state is a bug waiting for a bad request to trigger it.

### Normalize the schema. Avoid redundant data.
Follow 3NF where practical — every non-key field should depend on the whole key and nothing but the key. Don't store derived values as fields unless there is a clear performance reason and the derivation is documented. Calculated values like `available_balance`, `hygiene_balance`, and `total_price()` are properties and methods, not columns. If you find yourself syncing two fields that should always agree, that's a normalization problem.

### Use base classes to eliminate repeated fields.
`BaseModel` exists for a reason — it provides `active`, `created_at`, and `updated_at` to any model that needs them. Don't re-declare these fields on new models; inherit from `BaseModel`. If two or more models share a structural pattern (e.g., singleton settings, audit log entries), extract an abstract base class rather than duplicating the pattern.

### Write code that reads like the domain it models.
Method names should reflect the business action: `confirm_order()`, `consume_vouchers()`, `calculate_available_balance()`. Avoid generic names like `process()`, `handle()`, or `do_thing()`. A new developer should be able to read `Order.confirm()` → `Order._consume_vouchers()` and understand the business flow without reading comments. Keep methods short and focused — if a method needs a comment to explain what it's doing (not why), the method should be split.

---

## Architecture

Three distinct services:

| Service | Stack | Port | Purpose |
|---|---|---|---|
| **Django API** | Django 5.2.10 + DRF | 8000 | Backend API + legacy participant views |
| **Admin Frontend** | React + React-Admin + Vite | 5174 | Staff dashboard |
| **Participant Frontend** | React + Refine + Vite | 5173 | Participant shopping portal |

All API routes are versioned under `/api/v1/`. JWT auth via `djangorestframework-simplejwt`. The JWT token carries extra claims: `username`, `email`, `is_staff`, `is_superuser`, `groups`, `group_ids`.

---

## Running Locally

```bash
# Backend
source .venv/bin/activate
python manage.py runserver        # http://localhost:8000

# Admin frontend
cd frontend && npm run dev        # http://localhost:5174

# Participant frontend
cd participant-frontend && npm run dev  # http://localhost:5173
```

**Required `.env` keys** (see `.env` in project root — already configured for dev):
- `SECRET_KEY`, `DATABASE_URL`, `DOMAIN_NAME`, `HASHIDS_SALT`
- Dev uses SQLite (`db.sqlite3`) and console email backend
- `CELERY_TASK_ALWAYS_EAGER=True` in dev — no broker needed

---

## Django App Layout (`apps/`)

```
apps/
├── account/       # Participant & AccountBalance models, balance utils, customer numbers
├── pantry/        # Product catalog (Category, Product, Tag, GoFreshSettings), ordering UI
├── orders/        # Order, OrderItem, OrderVoucher; combined orders, packing lists
├── voucher/       # Voucher, VoucherSetting models and lifecycle
├── lifeskills/    # Program, ProgramPause; order window enforcement
├── log/           # EmailLog, OrderValidationLog, VoucherLog audit models
└── api/           # DRF router, shared permissions, pagination
```

`core/` holds settings, URLs, Celery config, signals, middleware, and the `OrderWindowSettings` singleton.

---

## Key Domain Concepts

### Balance Types
- **Available Balance** — Sum of up to 2 oldest `applied` grocery vouchers × their multipliers. Logic: `apps/account/utils/balance_utils.py`
- **Hygiene Balance** — `available_balance / 3` (reserved for hygiene products)
- **Go Fresh Balance** — Fixed per-order budget based on household size. Configured via `GoFreshSettings` singleton in `apps/pantry/models.py`

### Voucher Lifecycle
```
pending → applied → consumed
                  ↘ expired
```
Types: `grocery` or `life`. Only `applied` grocery vouchers count toward balance.

### VoucherSetting (singleton)
Defines `adult_amount`, `child_amount`, `infant_modifier` used to auto-calculate voucher amounts. Only one can be `active=True` at a time.

### Customer Numbers
Format: `C-XXX-D` (e.g., `C-BKM-7`). NATO-clear consonants only. Auto-generated on participant save. Implementation: `apps/account/utils/warehouse_id.py`.

### Order Windows
Orders can be restricted to a time window before a participant's class. `can_place_order(participant)` in `core/utils.py` returns `(bool, context)`.

### Combined Orders
Warehouse efficiency feature — consolidates confirmed orders for a program/date range into a single `CombinedOrder`. Triggered from admin or API.

### Signals (automatic workflows)
Key signals in `apps/account/signals.py` and `apps/voucher/signals.py`:
- New participant → create `AccountBalance`, generate vouchers, optionally create `User`, send onboarding email
- Participant household change (`adults`, `children`, `diaper_count`) → recalculate `base_balance`
- Voucher state changes → audit logged

---

## API Conventions

- Base URL: `/api/v1/`
- Auth: JWT Bearer token (`Authorization: Bearer <token>`)
- Pagination: `?page=1&page_size=25&ordering=-id`. Response includes `Content-Range` header for react-admin compatibility (`StandardResultsSetPagination` in `apps/api/pagination.py`)
- Filters: `django-filter` + `?search=` for text search
- Schema: `/api/v1/schema/` (OpenAPI), `/api/v1/docs/` (Swagger UI)
- JWT endpoints: `/api/v1/token/`, `/api/v1/token/refresh/`, `/api/v1/token/verify/`
- Login accepts `username` OR `customer_number` via `FlexibleTokenObtainPairSerializer`

### Permissions (`apps/api/permissions.py`)
- `IsStaffUser` — staff-only write access
- `IsAdminOrReadOnly` — read for authenticated, write for staff
- `IsOwnerOrAdmin` — object-level owner or staff
- `ReadOnlyPermission` — read-only (used for log models)
- `IsSingletonAdmin` — read for authenticated, write for staff (used for settings models)

---

## Frontend Details

### Admin Frontend (`frontend/`)
- React-Admin with custom `dataProvider` and `authProvider` in `frontend/src/providers/`
- `VITE_API_URL` env var sets the backend URL (defaults to `http://localhost:8000/api/v1`)
- Production base path is `/admin/` (set via `VITE_BASE_PATH`)
- Resources: participants, programs, orders, products, vouchers, categories, subcategories, combined-orders, packing-lists, tags, product-limits, groups, permissions, users

### Participant Frontend (`participant-frontend/`)
- Refine framework + MUI + TanStack Query
- `CartProvider` + `ValidationProvider` wrap protected routes
- `VITE_API_URL` defaults to `http://localhost:8000` (note: no `/api/v1` suffix here — the provider appends paths)
- Features: product browsing, cart, checkout, order history, account page

---

## Testing

```bash
# Full backend test suite with coverage
python -m pytest --cov=apps --cov-report=xml --cov-report=html

# Single file
python -m pytest apps/account/tests/test_account_balance.py -v

# Pattern match
python -m pytest -k "test_go_fresh" -v

# Frontend (admin)
cd frontend && npm test

# Frontend (participant)
cd participant-frontend && npm test
```

### Test conventions
- Uses `factory_boy` for fixtures. Key factories: `AccountBalanceFactory`, `ParticipantFactory`, `VoucherFactory`, `OrderFactory`, `ProductFactory`
- Many tests need `VoucherSettingFactory(active=True)` as an autouse fixture
- Celery tasks triggered by signals must be mocked in tests: patch `apps.account.tasks.onboarding.send_new_user_onboarding_email.delay`
- `pytest.ini` sets `DJANGO_SETTINGS_MODULE = core.settings` and `--reuse-db`

---

## Email System

- Dev: console backend (`EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'`)
- Prod: Mailgun via `django-anymail` (`MAILGUN_API_KEY`, `MAILGUN_SENDER_DOMAIN`)
- Templates stored in DB (`EmailType` model), editable via TinyMCE in admin. DB content overrides file templates.
- Email types: `onboarding`, `password_reset`, `order_confirmation`, `voucher_created`

---

## Deployment

Production target is **Render.com** (`render.yaml`). Runs:
- Django API via Gunicorn (`gunicorn core.wsgi:application`)
- Celery worker (separate service)
- PostgreSQL (Render managed DB)
- Redis (Render managed)
- Admin + participant frontends as static sites

Required prod env vars: `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `MAILGUN_API_KEY`, `MAILGUN_SENDER_DOMAIN`, `HASHIDS_SALT`, `RECAPTCHA_PUBLIC_KEY`, `RECAPTCHA_PRIVATE_KEY`

Static files collected to `staticfiles/`. S3-compatible object storage available (`USE_S3=True`).

---

## RBAC Groups

Seven default groups created by `python manage.py setup_groups`:

| Group | Key Permissions |
|---|---|
| Administrators | Full access (except superuser ops) |
| Order Managers | Full CRUD orders; view participants/products |
| Voucher Coordinators | Full CRUD vouchers; view participants |
| Program Coordinators | Full CRUD programs + participants |
| Inventory Managers | Full CRUD products + categories |
| Report Viewers | Read-only across all models |
| Support Staff | View/edit participants; view orders/vouchers |

---

## Common Gotchas

- **`VoucherSetting` must exist** — nearly every order validation path requires an active `VoucherSetting`. Tests missing this will fail unexpectedly.
- **Signals fire on every save** — balance recalculation and email tasks trigger automatically. Always mock email tasks in tests.
- **`--reuse-db`** — pytest reuses the test DB. Run with `--create-db` after schema changes.
- **Celery is eager in dev and tests** — tasks run synchronously. No broker needed locally.
- **`food_orders/` directory** — legacy, excluded from pytest (`norecursedirs`).
- **Admin frontend base path** — in production the build is served at `/admin/` not `/`. The `VITE_BASE_PATH` env var controls this.
- **`Content-Range` header** — react-admin requires this for pagination. `StandardResultsSetPagination` sets it automatically; custom views must too.

---

## Deployment Workflow

**Never deploy by building or pushing Docker images manually from a local machine.**

All production deployments go through git:

1. Push commits to `main` (or merge a PR)
2. GitHub Actions (`.github/workflows/frontend-ci.yml`) automatically:
   - Lints the frontend
   - Builds Docker images for both frontends with `VITE_API_URL=/api/v1` baked in
   - Pushes `parrishryan/basketful-admin:latest` and `parrishryan/basketful-participant:latest` to Docker Hub
3. SSH to the VPS and run `docker compose -f docker-compose.prod.images.yml pull && docker compose -f docker-compose.prod.images.yml up -d`

The frontend env var `VITE_API_URL` must always be `/api/v1` (relative). Nginx on the VPS proxies `/api/` to Django internally — an absolute URL like `http://localhost:8000` baked into a production image will cause CORS failures on any domain.

### Nginx Configuration

**Do not create or edit nginx config files in this repo.** The `nginx/` directory has been removed. All nginx configuration lives directly on the production server and is managed manually there. If you need to understand the routing, SSH to the server — do not recreate config files here.
