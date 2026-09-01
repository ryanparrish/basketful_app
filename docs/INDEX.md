# Basketful Application - Documentation Index

> Last updated: 2026-07-13

## 📚 Overview

This directory contains comprehensive documentation for the Basketful food pantry and voucher management application.

## 🗂️ Documentation Structure

### User Guides
- **[user-guides/ADDING_INDIVIDUAL_VOUCHER.md](user-guides/ADDING_INDIVIDUAL_VOUCHER.md)** - Step-by-step guide for staff: creating and applying a single voucher

### Architecture & Setup
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture, balance calculations, ER diagrams
- **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** - Folder layout and key files
- **[SETUP.md](SETUP.md)** - Development environment setup
- **[README.md](README.md)** - Project overview

### Core Systems
- **[ACCOUNT_BALANCES.md](ACCOUNT_BALANCES.md)** - Balance types and calculations (full, hygiene, Go Fresh)
- **[VOUCHER_SYSTEM.md](VOUCHER_SYSTEM.md)** - Voucher model, lifecycle, and consumption rules
- **[PRODUCT_ORDERING.md](PRODUCT_ORDERING.md)** - Product catalog and ordering flow
- **[ORDER_HISTORY.md](ORDER_HISTORY.md)** - Order tracking and validation logs

### Features
- **[GO_FRESH_BUDGET_FEATURE.md](GO_FRESH_BUDGET_FEATURE.md)** - Household-based fresh food budgets
- **[BULK_VOUCHER_CREATION.md](BULK_VOUCHER_CREATION.md)** - Batch voucher creation (React admin flow + legacy Django admin)
- **[BULK_PARTICIPANT_CREATE_WELCOME_CARDS.md](BULK_PARTICIPANT_CREATE_WELCOME_CARDS.md)** - Bulk participant intake + printable welcome cards (implemented)
- **[ORDER_WINDOW_FEATURE.md](ORDER_WINDOW_FEATURE.md)** - Time-based ordering restrictions (global/program/manual overrides)
- **[COMBINED_ORDER_FEATURE.md](COMBINED_ORDER_FEATURE.md)** - Combining and splitting multiple orders
- **[CUSTOMER_NUMBER_SYSTEM.md](CUSTOMER_NUMBER_SYSTEM.md)** - Warehouse-friendly IDs
- **[PROGRAM_PAUSES.md](PROGRAM_PAUSES.md)** - Program pause pre-boost multiplier + in-progress order block
- **[GROUPS_PERMISSIONS_IMPLEMENTATION.md](GROUPS_PERMISSIONS_IMPLEMENTATION.md)** - Groups/permissions model and the `/users/me/permissions/` API

### Infrastructure
- **[EMAIL_SYSTEM.md](EMAIL_SYSTEM.md)** - Email templates, Email Design Studio, and Mailgun sending
- **[MAILGUN_DELIVERY_INTELLIGENCE.md](MAILGUN_DELIVERY_INTELLIGENCE.md)** - Future: webhook event tracking, reachability scoring, participant inbox (roadmap; prerequisite now done)
- **[LOGGING_SYSTEM.md](LOGGING_SYSTEM.md)** - Audit logging and tracking
- **[FAILURE_ANALYTICS_GUIDE.md](FAILURE_ANALYTICS_GUIDE.md)** - Failed order attempts, idempotency, and distributed locking
- **[SIGNALS_AUTOMATION.md](SIGNALS_AUTOMATION.md)** - Django signals automation across all apps
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Render + Docker deployment

### Frontend
- **[PARTICIPANT_FRONTEND_BUILD.md](PARTICIPANT_FRONTEND_BUILD.md)** - Participant cart app (Refine, cookie-auth, i18n)

### Development
- **[TESTING.md](TESTING.md)** - Test commands, fixtures, and patterns
- **[CI.md](CI.md)** - GitHub Actions CI/CD pipeline

---

## 🎯 Quick Reference

### For Administrators

| Task | Documentation |
|------|--------------|
| Adding an individual voucher | [user-guides/ADDING_INDIVIDUAL_VOUCHER.md](user-guides/ADDING_INDIVIDUAL_VOUCHER.md) |
| Creating bulk vouchers | [BULK_VOUCHER_CREATION.md](BULK_VOUCHER_CREATION.md) |
| Setting order windows | [ORDER_WINDOW_FEATURE.md](ORDER_WINDOW_FEATURE.md) |
| Combining orders | [COMBINED_ORDER_FEATURE.md](COMBINED_ORDER_FEATURE.md) |
| Editing email templates | [EMAIL_SYSTEM.md](EMAIL_SYSTEM.md) |
| Managing Go Fresh budgets | [GO_FRESH_BUDGET_FEATURE.md](GO_FRESH_BUDGET_FEATURE.md) |

### For Developers

| Task | Documentation |
|------|--------------|
| Understanding architecture | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Finding code locations | [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) |
| Running tests | [TESTING.md](TESTING.md) |
| CI/CD configuration | [CI.md](CI.md) |
| Balance calculations | [ACCOUNT_BALANCES.md](ACCOUNT_BALANCES.md) |

---

## 📊 Data Models

See [ARCHITECTURE.md](ARCHITECTURE.md) for ER and class diagrams.

| Model | App | Description |
|-------|-----|-------------|
| `AccountBalance` | account | Participant balances |
| `GoFreshSettings` | account | Go Fresh budget thresholds |
| `HygieneSettings` | account | Hygiene balance ratio configuration |
| `Voucher` | voucher | Shopping vouchers |
| `VoucherSetting` | voucher | Global voucher configuration |
| `OrderVoucher` | voucher | Join table: which vouchers were consumed by an order |
| `Order` / `OrderItem` | orders | Participant orders and line items |
| `FailedOrderAttempt` | orders | Idempotency/failure log for order submission |
| `OrderWindowSettings` / `ProgramOrderWindow` / `ProgramWindowOverride` | orders | Global/program/manual order-window rules |
| `CombinedOrder` / `PackingSplitRule` / `PackingList` | orders | Multi-order combining and warehouse packing splits |
| `Product` | pantry | Catalog products |
| `Category` | pantry | Product categories |
| `ProgramPause` | lifeskills | Program pause periods (pre-pause boost + in-progress block) |

---

## 📝 Documentation Standards

All documentation should include:
- **Last updated** date at the top
- **Overview** section
- **Related Documentation** links at the bottom

---

## 📞 Support

For questions:
1. Check [ARCHITECTURE.md](ARCHITECTURE.md) for system overview
2. See [TESTING.md](TESTING.md) for debugging
3. Review [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) to find code
