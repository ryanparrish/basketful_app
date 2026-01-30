# Order History & Validation Logs

> Last updated: January 2026

This document describes order tracking and validation logging.

## Overview

The system maintains detailed records of orders and their validation history for auditing and debugging.

## Order Model

**Location:** `apps/orders/models.py::Order`

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `user` | ForeignKey | Participant who placed order |
| `status` | CharField | Order status |
| `total` | DecimalField | Order total amount |
| `hygiene_total` | DecimalField | Hygiene items subtotal |
| `go_fresh_total` | DecimalField | Go Fresh items subtotal |
| `created_at` | DateTimeField | Order creation timestamp |
| `confirmed_at` | DateTimeField | When order was confirmed |

### Order Statuses

| Status | Description |
|--------|-------------|
| `pending` | Order submitted, awaiting confirmation |
| `confirmed` | Order confirmed, vouchers consumed |
| `cancelled` | Order cancelled |
| `completed` | Order fulfilled |

## Order Items

**Location:** `apps/orders/models.py::OrderItem`

Each line item in an order with product, quantity, and price snapshot.

## Order Vouchers

**Location:** `apps/orders/models.py::OrderVoucher`

Junction table tracking which vouchers were applied to each order and the amount consumed from each.

## Validation Logs

**Location:** `apps/log/models.py::OrderValidationLog`

Records validation events during order processing:

| Field | Type | Description |
|-------|------|-------------|
| `order` | ForeignKey | Related order |
| `status` | CharField | Validation result |
| `message` | TextField | Detailed message |
| `created_at` | DateTimeField | Log timestamp |

### Log Statuses

- `success` — Validation passed
- `warning` — Non-blocking issue detected
- `error` — Validation failed

## Viewing Order History

### Admin Interface

Orders are managed via Django Admin at `/admin/orders/order/`

Features:
- Filter by status, date, participant
- Inline order items view
- Validation log inline

### Participant View

Participants can view their order history in their account dashboard.

## Combined Orders

Multiple orders can be combined for a single participant.

See [COMBINED_ORDER_FEATURE.md](COMBINED_ORDER_FEATURE.md) for details.

## Related Documentation

- [LOGGING_SYSTEM.md](LOGGING_SYSTEM.md) — General logging
- [COMBINED_ORDER_FEATURE.md](COMBINED_ORDER_FEATURE.md) — Order combining
- [PRODUCT_ORDERING.md](PRODUCT_ORDERING.md) — Placing orders
