# Product Ordering

> Last updated: January 2026

This document describes the product catalog and ordering flow.

## Overview

The ordering system allows participants to browse products by category and build shopping carts within their available balance limits.

## Product Model

**Location:** `apps/pantry/models.py::Product`

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | CharField | Product display name |
| `price` | DecimalField | Unit price |
| `category` | ForeignKey | Product category |
| `tags` | ManyToMany | Product tags for filtering |
| `is_active` | BooleanField | Whether product is available |

## Categories

**Location:** `apps/pantry/models.py::Category`

Categories organize products and can have special balance rules (e.g., hygiene-only categories).

### Protected Categories

Some categories are protected from deletion or modification via admin. See category protection tests for details.

## Ordering Flow

1. **Browse** — Participant views products by category
2. **Add to Cart** — Products added with quantity validation
3. **Balance Check** — Cart validated against available balances
4. **Submit Order** — Order created in pending state
5. **Confirm** — Admin confirms, vouchers consumed

## Cart Validation

The cart enforces multiple balance constraints:

- **Total** cannot exceed available balance
- **Hygiene items** cannot exceed hygiene balance
- **Go Fresh items** cannot exceed Go Fresh balance (when enabled)

**Implementation:** `apps/orders/models.py::Order.clean()`

## Mobile UI

The primary ordering interface is mobile-optimized:

**Template:** `apps/pantry/templates/food_orders/create_order.html`

Features:
- Category navigation
- Real-time balance display
- Cart drawer with balance breakdown
- AJAX cart updates

## Order Window

Orders can only be placed during configured order windows.

See [ORDER_WINDOW_FEATURE.md](ORDER_WINDOW_FEATURE.md) for details.

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — System overview
- [ACCOUNT_BALANCES.md](ACCOUNT_BALANCES.md) — Balance constraints
- [ORDER_WINDOW_FEATURE.md](ORDER_WINDOW_FEATURE.md) — Ordering schedule
- [GO_FRESH_BUDGET_FEATURE.md](GO_FRESH_BUDGET_FEATURE.md) — Fresh food budget
