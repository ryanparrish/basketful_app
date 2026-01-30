# Basketful Application - Feature Documentation Index

## 📚 Overview
This directory contains comprehensive documentation for all features, fixes, and technical implementations in the Basketful application.

## 🗂️ Documentation Structure

### Core Features
- **[BULK_VOUCHER_CREATION.md](BULK_VOUCHER_CREATION.md)** - Bulk voucher creation for programs
- **[ORDER_WINDOW_FEATURE.md](ORDER_WINDOW_FEATURE.md)** - Time-based order window restrictions
- **[COMBINED_ORDER_FEATURE.md](COMBINED_ORDER_FEATURE.md)** - Combined order creation and management
- **[CUSTOMER_NUMBER_SYSTEM.md](CUSTOMER_NUMBER_SYSTEM.md)** - Warehouse-friendly customer ID system

### Bug Fixes & Improvements
- **[BUGS_FOUND.md](BUGS_FOUND.md)** - Cart edge case bugs discovered
- **[CART_SEARCH_BUG.md](CART_SEARCH_BUG.md)** - Search filter hiding cart items fix
- **[CART_VALIDATION.md](CART_VALIDATION.md)** - Cart data flow validation
- **[IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md)** - Cart search fix implementation

### Infrastructure & Testing
- **[CI_SETUP.md](CI_SETUP.md)** - CI/CD pipeline configuration
- **[CI.md](CI.md)** - Continuous integration details
- **[CI_FIXES_SUMMARY.md](CI_FIXES_SUMMARY.md)** - CI test fixes
- **[TESTING.md](TESTING.md)** - Testing strategy and commands
- **[TEST_FIXES.md](TEST_FIXES.md)** - Test suite fixes
- **[TEST_FIXES_SIGNAL_ISSUES.md](TEST_FIXES_SIGNAL_ISSUES.md)** - Signal-related test fixes

### Architecture & Setup
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture overview
- **[SETUP.md](SETUP.md)** - Development environment setup
- **[README.md](README.md)** - Project overview

### Additional Features
- **[EMAIL_SYSTEM.md](EMAIL_SYSTEM.md)** - Configurable email templates
- **[LOGGING_SYSTEM.md](LOGGING_SYSTEM.md)** - Audit logging and tracking
- **[SIGNALS_AUTOMATION.md](SIGNALS_AUTOMATION.md)** - Django signals and automation

---

## 🎯 Feature Categories

### Admin Features
| Feature | Documentation | Description |
|---------|--------------|-------------|
| Bulk Voucher Creation | [BULK_VOUCHER_CREATION.md](BULK_VOUCHER_CREATION.md) | Create vouchers for all participants in a program |
| Combined Orders | [COMBINED_ORDER_FEATURE.md](COMBINED_ORDER_FEATURE.md) | Combine multiple orders into one |
| Order Window | [ORDER_WINDOW_FEATURE.md](ORDER_WINDOW_FEATURE.md) | Control when participants can order |
| Email Templates | [EMAIL_SYSTEM.md](EMAIL_SYSTEM.md) | Manage email templates from admin |
| Customer Numbers | [CUSTOMER_NUMBER_SYSTEM.md](CUSTOMER_NUMBER_SYSTEM.md) | Generate warehouse-friendly IDs |
| Go Fresh Budget | [GO_FRESH_BUDGET_FEATURE.md](GO_FRESH_BUDGET_FEATURE.md) | Household-based fresh food budgets |

### User Features
| Feature | Documentation | Description |
|---------|--------------|-------------|
| Product Ordering | - | Browse and order products |
| Cart Management | [CART_VALIDATION.md](CART_VALIDATION.md) | Shopping cart with persistence |
| Voucher Application | - | Automatic voucher management |
| Order History | - | View past orders |

### System Features
| Feature | Documentation | Description |
|---------|--------------|-------------|
| Audit Logging | [LOGGING_SYSTEM.md](LOGGING_SYSTEM.md) | Track all system changes |
| Auto-Vouchers | [SIGNALS_AUTOMATION.md](SIGNALS_AUTOMATION.md) | Automatic voucher creation |
| Account Balances | - | Real-time balance tracking |
| Program Pauses | - | Voucher multipliers during pauses |

---

## 🔧 Technical Documentation

### Data Models
- **Participant** - Program participants with household info
- **AccountBalance** - Participant account balances
- **Order** - Individual participant orders
- **Voucher** - Food/hygiene vouchers
- **Product** - Pantry products with categories
- **Program** - Weekly class programs
- **EmailType** - Configurable email templates

### Custom Admin Features
- **Bulk Actions** - Bulk voucher creation, user creation
- **Custom Views** - Combined order creation, email preview
- **Print Views** - Order print view with customer numbers
- **Inlines** - Order items, voucher logs

### Automation
- **Signals** - Auto-create accounts, vouchers, user profiles
- **Tasks** - Email sending (Celery integration ready)
- **Management Commands** - Database seeding

---

## 📖 Quick Reference

### For Administrators
1. **Creating Bulk Vouchers**: See [BULK_VOUCHER_CREATION.md](BULK_VOUCHER_CREATION.md)
2. **Setting Order Windows**: See [ORDER_WINDOW_FEATURE.md](ORDER_WINDOW_FEATURE.md)
3. **Combining Orders**: See [COMBINED_ORDER_FEATURE.md](COMBINED_ORDER_FEATURE.md)
4. **Editing Email Templates**: See [EMAIL_SYSTEM.md](EMAIL_SYSTEM.md)

### For Developers
1. **Setup Environment**: See [SETUP.md](SETUP.md)
2. **Run Tests**: See [TESTING.md](TESTING.md)
3. **Architecture**: See [ARCHITECTURE.md](ARCHITECTURE.md)
4. **CI/CD**: See [CI_SETUP.md](CI_SETUP.md)

### For Bug Reports
1. **Cart Issues**: See [BUGS_FOUND.md](BUGS_FOUND.md)
2. **Search Bug**: See [CART_SEARCH_BUG.md](CART_SEARCH_BUG.md)
3. **Test Fixes**: See [TEST_FIXES.md](TEST_FIXES.md)

---

## 📝 Documentation Standards

All feature documentation should include:
- **Overview** - What the feature does
- **Access** - How to access the feature
- **Workflow** - Step-by-step usage
- **Technical Details** - Implementation specifics
- **Files Modified** - Code changes made
- **Testing** - How to test the feature

---

## 🔄 Recent Updates

### January 17, 2026
- ✅ Added bulk voucher creation feature
- ✅ Updated order print view with customer numbers
- ✅ Consolidated all documentation to docs/ folder
- ✅ Created comprehensive documentation index

### Previous
- Order window feature implementation
- Combined order creation
- Cart search bug fix
- Customer number system
- CI/CD pipeline setup

---

## 📞 Support

For questions or issues:
1. Check relevant documentation in this folder
2. Review [ARCHITECTURE.md](ARCHITECTURE.md) for system overview
3. See [TESTING.md](TESTING.md) for debugging help
