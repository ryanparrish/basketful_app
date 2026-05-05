# Basketful — Behaviour Registry & Test Coverage

> **Why this file exists**: Basketful serves vulnerable people at food pantries.
> No participant should ever have to fear that a broken app or broken experience
> will put their food assistance at risk.
> This document is the **single source of truth** for what behaviours are tested,
> where the tests live, and what still needs to be covered.
>
> **Rules**:
> - `[x]` = behaviour has at least one passing test — add the test ID next to it.
> - `[ ]` = known behaviour, untested. This is a gap.
> - `[~]` = partially tested — happy path exists, edge cases missing.
> - Adding a test without updating this file is **incomplete work**.
> - This file is read by the `write-tests` agent before every test-writing session.

**Last audited**: 2026-05-01 (BEH-069, BEH-210–212 covered — participant frontend test infrastructure added)
**Backend**: `pytest` (see `pytest.ini`) — run with `pytest --tb=short -v`
**Frontend**: `vitest` (see `frontend/vitest.config.js`) — run with `npm test -- --run`
**CI**: `.github/workflows/ci.yml` (backend), `.github/workflows/frontend-ci.yml` (frontend)

---

## Table of Contents

1. [How to Run Tests](#how-to-run-tests)
2. [Factory Index](#factory-index)
3. [Behaviour Domains](#behaviour-domains)
   - [BEH-001–016 Order Placement](#beh-001016-order-placement)
   - [BEH-020–027 Voucher Integrity](#beh-020027-voucher-integrity)
   - [BEH-030–039 Balance Calculations](#beh-030039-balance-calculations)
   - [BEH-040–051 Participant Data Integrity](#beh-040051-participant-data-integrity)
   - [BEH-060–070 Authentication & Access Control](#beh-060070-authentication--access-control)
   - [BEH-080–090 Order Windows](#beh-080090-order-windows)
   - [BEH-100–107 Program Pause](#beh-100107-program-pause)
   - [BEH-110–120 GoFresh Budget](#beh-110120-gofresh-budget)
   - [BEH-130–134 Hygiene / Input Validation](#beh-130134-hygiene--input-validation)
   - [BEH-140–144 Combined Orders](#beh-140144-combined-orders)
   - [BEH-150–156 Email / Notifications](#beh-150156-email--notifications)
   - [BEH-160–166 Logging](#beh-160166-logging)
   - [BEH-170–181 Admin API](#beh-170181-admin-api)
   - [BEH-190–195 Frontend — ManualOverridePanel](#beh-190195-frontend--manualoverridepanel)
   - [BEH-200–203 Frontend — Participant Edit](#beh-200203-frontend--participant-edit)
4. [CI Gates](#ci-gates)
5. [Priority Queue](#priority-queue)

---

## How to Run Tests

```bash
# Full backend suite with coverage
source .venv/bin/activate
pytest --tb=short -v --cov=apps --cov-report=term-missing

# Single app
pytest apps/orders/ -v

# Pattern match
pytest -k "balance" -v

# Frontend (React Admin)
cd frontend && npm test -- --run

# Frontend (Participant)
cd participant-frontend && npm test -- --run
```

---

## Factory Index

| Factory | Module | Key Traits / Params |
|---------|--------|---------------------|
| `UserFactory` | `apps/orders/tests/factories.py` | default: non-staff; `.staff` trait |
| `ParticipantFactory` | `apps/orders/tests/factories.py` | `user=` kwarg to link User |
| `AccountBalanceFactory` | `apps/orders/tests/factories.py` | `participant=` |
| `VoucherFactory` | `apps/orders/tests/factories.py` | `state=`, `voucher_amnt=` |
| `VoucherSettingFactory` | `apps/voucher/tests/factories.py` | `active=True` required by many tests |
| `OrderFactory` | `apps/orders/tests/factories.py` | `participant=`, `status=` |
| `OrderItemFactory` | `apps/orders/tests/factories.py` | `order=`, `quantity=` |
| `CategoryFactory` | `apps/pantry/tests/factories.py` | — |
| `ProductFactory` | `apps/pantry/tests/factories.py` | `category=`, `is_go_fresh=` |
| `ProgramWindowOverrideFactory` | ⚠️ **MISSING — needs to be created** | `expires_at=`, `participant=` |

---

## Behaviour Domains

Legend: `[x]` covered · `[ ]` gap · `[~]` partially covered

---

### BEH-001–016 Order Placement

| ID | Behaviour | Status | Test |
|----|-----------|--------|------|
| BEH-001 | Participant can place an order when balance ≥ total | `[x]` | `apps/orders/tests/test_order_validation.py::TestOrderValidation::test_valid_order` |
| BEH-002 | Order total is correctly summed from line items | `[x]` | `apps/orders/tests/test_order_validation.py::TestOrderValidation::test_order_total_calculation` |
| BEH-003 | Order is rejected when total exceeds available balance | `[x]` | `apps/orders/tests/test_order_validation.py::TestOrderValidation::test_order_exceeds_balance` |
| BEH-004 | Order status transitions: `pending → submitted → fulfilled` are enforced | `[ ]` | — |
| BEH-005a | Second order attempt while a pending order exists is rejected | `[x]` | `apps/orders/tests/test_duplicate_order.py::TestDuplicateOrderGuard::test_second_pending_order_for_same_participant_is_rejected` |
| BEH-005b | Second order attempt while a confirmed order exists is rejected | `[x]` | `apps/orders/tests/test_duplicate_order.py::TestDuplicateOrderGuard::test_second_order_while_confirmed_order_exists_is_rejected` |
| BEH-005c | Cancelled order does NOT block a new order (over-block guard) | `[x]` | `apps/orders/tests/test_duplicate_order.py::TestDuplicateOrderGuard::test_new_order_allowed_after_previous_order_is_cancelled` |
| BEH-005d | Race condition — two simultaneous POSTs for same participant → only one succeeds (requires DB-level unique constraint) | `[ ]` | — |
| BEH-006 | Order with zero-quantity item is rejected | `[ ]` | — |
| BEH-007 | Order with negative-quantity item is rejected | `[ ]` | — |
| BEH-008 | Cancelled order does not deduct balance | `[ ]` | — |
| BEH-009 | Fulfilled order deducts balance exactly once | `[~]` | `apps/orders/tests/test_order_validation.py` (happy path only) |
| BEH-010 | `OrderItem.unit_price` is captured at time of ordering, not at current product price | `[ ]` | — |
| BEH-011 | Out-of-stock product cannot be added to order | `[ ]` | — |
| BEH-012 | Order API returns 403 for unauthenticated request | `[ ]` | — |
| BEH-013 | Participant with zero balance is blocked from placing any order | `[ ]` | — |
| BEH-014 | Order API returns 404 for order belonging to another participant (IDOR) | `[ ]` | — |
| BEH-015 | Staff user can view all orders regardless of participant | `[ ]` | — |
| BEH-016 | Order total is recalculated on PUT/PATCH to prevent client-side spoofing | `[ ]` | — |

---

### BEH-020–027 Voucher Integrity

| ID | Behaviour | Status | Test |
|----|-----------|--------|------|
| BEH-020 | Voucher in `applied` state increases available balance | `[x]` | `apps/account/tests/test_account_balance.py::TestAvailableBalance::test_available_balance_with_voucher` |
| BEH-021 | Voucher in `redeemed` state does NOT increase available balance | `[x]` | `apps/account/tests/test_account_balance.py::TestAvailableBalance::test_redeemed_voucher_excluded` |
| BEH-022 | Voucher in `expired` state does NOT increase available balance | `[~]` | partial in `test_account_balance.py` |
| BEH-023 | Voucher `expires_at` in the past is automatically expired | `[ ]` | — |
| BEH-024 | Two vouchers for the same participant sum correctly | `[x]` | `apps/account/tests/test_account_balance.py` |
| BEH-025 | Voucher amount is immutable once `applied` | `[ ]` | — |
| BEH-026 | Bulk voucher creation creates the correct count of vouchers | `[ ]` | — |
| BEH-027 | Voucher for wrong participant cannot be redeemed by another participant | `[ ]` | — |

---

### BEH-030–039 Balance Calculations

| ID | Behaviour | Status | Test |
|----|-----------|--------|------|
| BEH-030 | `available_balance` = sum of `applied` vouchers minus fulfilled order totals | `[x]` | `apps/account/tests/test_account_balance.py::TestAvailableBalance` |
| BEH-031 | `available_balance` rounds to 2 decimal places | `[ ]` | — |
| BEH-032 | `available_balance` is never negative | `[ ]` | — |
| BEH-033 | Balance is 0 for participant with no vouchers | `[x]` | `apps/account/tests/test_account_balance.py::TestAvailableBalance::test_no_vouchers` |
| BEH-034 | Balance is correctly recalculated after order fulfilment | `[ ]` | — |
| BEH-035 | Balance calculation ignores `pending` (unsubmitted) orders | `[ ]` | — |
| BEH-036 | GoFresh budget is tracked separately from main voucher balance | `[~]` | `apps/orders/tests/test_go_fresh_validation.py` |
| BEH-037 | GoFresh budget does not bleed into general balance | `[x]` | `apps/orders/tests/test_go_fresh_validation.py::TestGoFreshValidation` |
| BEH-038 | Balance API returns 403 for unauthenticated request | `[ ]` | — |
| BEH-039 | Balance API returns 404 for another participant's balance (IDOR) | `[ ]` | — |

---

### BEH-040–051 Participant Data Integrity

| ID | Behaviour | Status | Test |
|----|-----------|--------|------|
| BEH-040 | Creating a Participant creates a linked User | `[ ]` | — |
| BEH-041 | `Participant.email` must be unique across all participants | `[ ]` | — |
| BEH-042 | `Participant.customer_number` is assigned automatically | `[ ]` | — |
| BEH-043 | `Participant.customer_number` is unique | `[ ]` | — |
| BEH-044 | Updating `Participant.email` syncs `User.email` (regression: email sync signal) | `[ ]` | — |
| BEH-045 | Updating `Participant.email` to an address already used by another User is rejected | `[ ]` | — |
| BEH-046 | Staff can update participant without affecting their own session | `[ ]` | — |
| BEH-047 | Participant cannot update another participant's profile (IDOR) | `[ ]` | — |
| BEH-048 | Deleting a Participant cascades correctly (balance, orders, vouchers) | `[ ]` | — |
| BEH-049 | Participant with `is_active=False` cannot authenticate | `[ ]` | — |
| BEH-050 | Participant API returns only the requesting participant's own data | `[ ]` | — |
| BEH-051 | `high_balance_flag` is set when balance exceeds threshold | `[ ]` | — |

---

### BEH-060–070 Authentication & Access Control

| ID | Behaviour | Status | Test |
|----|-----------|--------|------|
| BEH-060 | Valid credentials return `access_token` + `refresh_token` as httpOnly cookies | `[ ]` | — |
| BEH-061 | Invalid credentials return 401 | `[ ]` | — |
| BEH-062 | Expired `access_token` cookie returns 401 | `[ ]` | — |
| BEH-063 | Valid `refresh_token` rotates to a new `access_token` | `[ ]` | — |
| BEH-064 | Logout clears both cookies | `[ ]` | — |
| BEH-065 | reCAPTCHA token is validated server-side on login — missing token returns 400 | `[ ]` | — |
| BEH-066 | Rate limiter blocks >5 failed login attempts from same IP | `[ ]` | — |
| BEH-067 | All protected API endpoints reject Bearer-header auth (cookie-only in prod) | `[ ]` | — |
| BEH-068 | Staff-only endpoints return 403 for participant-role users | `[ ]` | — |
| BEH-069 | Participant A cannot read Participant B's orders | `[x]` | `participant-frontend/src/features/orders/__tests__/OrderHistory.test.tsx::BEH-069` |
| BEH-070 | Participant A cannot read Participant B's balance | `[ ]` | — |

---

### BEH-080–090 Order Windows

| ID | Behaviour | Status | Test |
|----|-----------|--------|------|
| BEH-080 | Orders cannot be placed outside an active order window | `[ ]` | — |
| BEH-081 | Orders can be placed during an active order window | `[ ]` | — |
| BEH-082 | Order window with `is_active=False` blocks ordering | `[ ]` | — |
| BEH-083 | Staff can create a manual override window | `[ ]` | — |
| BEH-084 | Manual override with a future `expires_at` is accepted | `[ ]` | — |
| BEH-085 | Manual override with a past `expires_at` is rejected with 400 | `[ ]` | — |
| BEH-086 | Override API accepts a naive ISO datetime string and returns 200, not 500 (regression: `make_aware` fix) | `[ ]` | — |
| BEH-087 | Expired override is no longer effective after `expires_at` | `[ ]` | — |
| BEH-088 | Override is scoped to a specific participant, not global | `[ ]` | — |
| BEH-089 | Deleting an override re-applies the global window restriction | `[ ]` | — |
| BEH-090 | Order window dates are stored as timezone-aware datetimes | `[ ]` | — |

---

### BEH-100–107 Program Pause

| ID | Behaviour | Status | Test |
|----|-----------|--------|------|
| BEH-100 | Active program pause blocks all new orders for that program | `[x]` | `apps/lifeskills/tests/test_program_pause.py` |
| BEH-101 | Deactivating a pause re-enables ordering | `[x]` | `apps/lifeskills/tests/test_program_pause.py` |
| BEH-102 | Pause affects only its targeted program, not others | `[ ]` | — |
| BEH-103 | Multiple pauses — only one active at a time per program | `[ ]` | — |
| BEH-104 | Creating a pause via API requires staff permission | `[ ]` | — |
| BEH-105 | Pause start date in the future does not block orders today | `[ ]` | — |
| BEH-106 | Pause with `end_date` in the past is treated as inactive | `[ ]` | — |
| BEH-107 | Paused program returns descriptive error, not 500 | `[ ]` | — |

---

### BEH-110–120 GoFresh Budget

| ID | Behaviour | Status | Test |
|----|-----------|--------|------|
| BEH-110 | Participant receives correct GoFresh budget for household size | `[x]` | `apps/orders/tests/test_go_fresh_validation.py::TestGoFreshValidation` |
| BEH-111 | GoFresh budget is not available to participants without eligibility | `[x]` | `apps/orders/tests/test_go_fresh_validation.py` |
| BEH-112 | GoFresh items can only be paid from GoFresh budget, not main balance | `[x]` | `apps/orders/tests/test_go_fresh_validation.py` |
| BEH-113 | Main-balance items cannot be paid from GoFresh budget | `[x]` | `apps/orders/tests/test_go_fresh_validation.py` |
| BEH-114 | GoFresh budget is reset correctly at the start of each window | `[ ]` | — |
| BEH-115 | GoFresh product flag `is_go_fresh=True` is enforced in ordering logic | `[~]` | `apps/pantry/tests/test_go_fresh_settings.py` |
| BEH-116 | GoFresh-only window does not allow non-GoFresh items | `[ ]` | — |
| BEH-117 | GoFresh budget max is capped even when household size is very large | `[ ]` | — |
| BEH-118 | GoFresh budget API returns 403 for unauthenticated request | `[ ]` | — |
| BEH-119 | GoFresh settings update affects next order, not already-placed orders | `[ ]` | — |
| BEH-120 | GoFresh budget = 0 if `GoFreshSettings.enabled = False` | `[ ]` | — |

---

### BEH-130–134 Hygiene / Input Validation

| ID | Behaviour | Status | Test |
|----|-----------|--------|------|
| BEH-130 | Decimal money fields reject values with more than 2 decimal places | `[ ]` | — |
| BEH-131 | Decimal money fields reject negative values | `[ ]` | — |
| BEH-132 | String fields are stripped of leading/trailing whitespace before save | `[ ]` | — |
| BEH-133 | Email fields are lowercased and stripped before save | `[ ]` | — |
| BEH-134 | Phone number fields are validated to E.164 format | `[ ]` | — |

---

### BEH-140–144 Combined Orders

| ID | Behaviour | Status | Test |
|----|-----------|--------|------|
| BEH-140 | Combined order totals both GoFresh and standard budgets correctly | `[x]` | `apps/orders/tests/test_combined_orders.py::TestCombinedOrders` |
| BEH-141 | Combined order respects per-category limits | `[x]` | `apps/orders/tests/test_combined_orders.py` |
| BEH-142 | Removing a GoFresh item from a combined order recalculates GoFresh total | `[ ]` | — |
| BEH-143 | Combined order with $0 GoFresh portion is still valid | `[ ]` | — |
| BEH-144 | Combined order is rejected if either sub-total exceeds its respective budget | `[x]` | `apps/orders/tests/test_combined_orders.py` |

---

### BEH-150–156 Email / Notifications

| ID | Behaviour | Status | Test |
|----|-----------|--------|------|
| BEH-150 | New participant triggers welcome email (Celery task enqueued) | `[ ]` | — |
| BEH-151 | Welcome email is sent to `User.email`, not `Participant.email` directly | `[ ]` | — |
| BEH-152 | Order confirmation email is enqueued on order submission | `[ ]` | — |
| BEH-153 | Email is not sent when `CELERY_TASK_ALWAYS_EAGER=False` in background context | `[ ]` | — |
| BEH-154 | Emails are never sent during test runs unless explicitly asserted | `[ ]` | — |
| BEH-155 | Changing participant email does not break email delivery (post-sync signal) | `[ ]` | — |
| BEH-156 | Email template renders participant name and balance correctly | `[ ]` | — |

---

### BEH-160–166 Logging

| ID | Behaviour | Status | Test |
|----|-----------|--------|------|
| BEH-160 | Order placement is logged with participant ID and order ID | `[ ]` | — |
| BEH-161 | Failed order attempt (balance exceeded) is logged | `[ ]` | — |
| BEH-162 | Authentication failure is logged with IP address | `[ ]` | — |
| BEH-163 | Log entries never contain plaintext passwords or full tokens | `[ ]` | — |
| BEH-164 | Log entries never contain full credit card / financial account numbers | `[ ]` | — |
| BEH-165 | Admin actions (participant edit, voucher create) are logged | `[ ]` | — |
| BEH-166 | Log viewer API is restricted to staff only | `[ ]` | — |

---

### BEH-170–181 Admin API

| ID | Behaviour | Status | Test |
|----|-----------|--------|------|
| BEH-170 | Staff can create a participant via POST `/api/participants/` | `[ ]` | — |
| BEH-171 | Staff can update a participant via PUT/PATCH `/api/participants/{id}/` | `[ ]` | — |
| BEH-172 | Participant list is paginated and not unbounded | `[ ]` | — |
| BEH-173 | Participant search by name/email returns correct results | `[ ]` | — |
| BEH-174 | Staff can create a voucher and assign it to a participant | `[ ]` | — |
| BEH-175 | Staff can bulk-create vouchers | `[ ]` | — |
| BEH-176 | Staff can view all orders for all participants | `[ ]` | — |
| BEH-177 | Staff cannot delete a participant with open orders | `[ ]` | — |
| BEH-178 | Non-staff authenticated user cannot access admin endpoints | `[ ]` | — |
| BEH-179 | Unauthenticated request to admin endpoints returns 401 | `[ ]` | — |
| BEH-180 | Admin serializers use explicit `fields` — no `__all__` on writable endpoints | `[ ]` | — |
| BEH-181 | Mass-assignment: extra fields in POST body are silently ignored | `[ ]` | — |

---

### BEH-190–195 Frontend — ManualOverridePanel

| ID | Behaviour | Status | Test |
|----|-----------|--------|------|
| BEH-190 | Panel renders without crashing when no override exists | `[ ]` | — |
| BEH-191 | Panel renders with current override data pre-populated | `[ ]` | — |
| BEH-192 | Submit with valid datetime calls POST and shows success toast | `[ ]` | — |
| BEH-193 | Submit with past datetime shows validation error, does not POST | `[ ]` | — |
| BEH-194 | Delete button calls DELETE and clears form | `[ ]` | — |
| BEH-195 | API error (500) is caught and displayed as user-facing error message | `[ ]` | — |

---

### BEH-200–203 Frontend — Participant Edit

| ID | Behaviour | Status | Test |
|----|-----------|--------|------|
| BEH-200 | Editing participant name saves and re-renders updated name | `[ ]` | — |
| BEH-201 | Editing participant email saves and shows new email in form | `[ ]` | — |
| BEH-202 | Submitting duplicate email shows server-side validation error | `[ ]` | — |
| BEH-203 | Cancelled edit does not persist changes | `[ ]` | — |

---

## CI Gates

| Gate | Status | Config |
|------|--------|--------|
| Backend pytest passes | ✅ enforced | `.github/workflows/ci.yml` |
| Backend coverage ≥ 80% | ⚠️ reported, NOT blocking (`fail_ci_if_error: false`) | `codecov.yml` |
| Admin frontend build passes | ✅ enforced | `.github/workflows/frontend-ci.yml` |
| Admin frontend tests pass | ❌ **MISSING — no `npm test` step in frontend-ci.yml** | — |
| Participant frontend build passes | ✅ enforced | `.github/workflows/frontend-ci.yml` |
| Participant frontend tests pass | ❌ **MISSING** | — |

**Open CI gap**: Add `npm test -- --run` step to `.github/workflows/frontend-ci.yml` for both matrix entries.

---

### BEH-210–212 Frontend — Participant Order History

| ID | Behaviour | Status | Test |
|----|-----------|--------|------|
| BEH-210 | `OrderHistory` renders one `OrderCard` per order returned by the API | `[x]` | `participant-frontend/src/features/orders/__tests__/OrderHistory.test.tsx::BEH-210` |
| BEH-211 | `OrderHistory` shows empty-state UI when API returns zero orders | `[x]` | `participant-frontend/src/features/orders/__tests__/OrderHistory.test.tsx::BEH-211` |
| BEH-212 | `OrderHistory` shows error alert when the API call fails | `[x]` | `participant-frontend/src/features/orders/__tests__/OrderHistory.test.tsx::BEH-212` |

---

## Priority Queue

Work the 🔴 items before moving to 🟠. Do not skip.

### 🔴 CRITICAL — Fix before next release

| ID | Why Critical | Prerequisite |
|----|-------------|--------------|
| BEH-044 | Regression test for email sync signal added this session | Add `with_user` trait to `ParticipantFactory` |
| BEH-013 | Zero-balance participant blocked from ordering — core access control | None |
| BEH-070 | IDOR — participant cannot read another participant's balance | None |
| BEH-086 | Regression for `make_aware` fix — naive datetime → 200 not 500 | `ProgramWindowOverrideFactory` |
| BEH-005d | Race condition — two simultaneous POSTs → only one order created | DB-level unique constraint decision needed |

### 🟠 HIGH — Next sprint

| ID | Why |
|----|-----|
| BEH-003 | Balance guard on order placement — most critical business rule |
| BEH-062 | Expired token handling — auth robustness |
| BEH-065 | reCAPTCHA server-side validation |
| BEH-066 | Login rate limiting brute-force protection |
| BEH-163 | No PII in logs — compliance |

### 🟡 MEDIUM — Within 30 days

| ID | Why |
|----|-----|
| BEH-004 | Order state machine integrity |
| BEH-023 | Voucher auto-expiry |
| BEH-105 | Future-dated pause does not block orders today |
| BEH-114 | GoFresh budget reset per window |
| BEH-150 | Welcome email enqueued |

### 🔵 LOW — Hardening

| ID | Why |
|----|-----|
| BEH-130–134 | Input hygiene |
| BEH-156 | Email template rendering |
| BEH-172 | Pagination on participant list |
| BEH-190–195 | ManualOverridePanel frontend tests |

## Related Documentation

- [CI.md](CI.md) — CI/CD workflow configuration
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) — Test file locations