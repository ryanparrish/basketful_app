# Basketful - Food Pantry Management System

[![codecov](https://codecov.io/gh/ryanparrish/basketful_app/branch/main/graph/badge.svg)](https://codecov.io/gh/ryanparrish/basketful_app)
[![CI](https://github.com/ryanparrish/basketful_app/workflows/CI%20-%20Test%20and%20Lint/badge.svg)](https://github.com/ryanparrish/basketful_app/actions)
[![Mutation Testing](https://img.shields.io/badge/mutation-pending-yellow)](https://github.com/ryanparrish/basketful_app/actions/workflows/mutation-testing.yml)

Basketful is a comprehensive Django-based application for managing food pantry operations, participant accounts, vouchers, and orders.

## Features

### Participant Management
Track individual participants with household information, eligibility, needs, and associated accounts. Automatically generates warehouse-friendly customer numbers.

### Ordering System
- Product browsing with categories and search
- Shopping cart with localStorage persistence
- Order validation and voucher application
- Order window restrictions by class schedule
- Combined orders for warehouse efficiency

### Voucher Management
- Automatic voucher creation and application
- Support for grocery and hygiene vouchers
- Bulk voucher creation by program
- Program pause logic with multipliers
- Real-time balance tracking

### Account Balances
- Dynamic balance calculation based on household size
- Hygiene balance separation (1/3 of total)
- Available balance with recent voucher logic
- Automatic updates via Django signals

### Admin Tools
- Custom bulk actions (voucher creation, user management)
- Print-friendly order views with customer numbers
- AJAX-enhanced interfaces
- Email template management
- Comprehensive audit logging

### Automation
- Auto-create accounts for new participants
- Auto-generate vouchers based on household
- Auto-calculate balances on household changes
- Auto-send onboarding and notification emails

## Tech Stack

- **Backend**: Django 5.2.10
- **Database**: PostgreSQL (production), SQLite (development)
- **Containerization**: Docker
- **Frontend**: Django Admin + Bootstrap + AJAX
- **Email**: SMTP with TinyMCE templates
- **Testing**: pytest + Jest
- **CI/CD**: GitHub Actions + Docker Hub

## Documentation

📖 **[Complete Documentation Index](docs/INDEX.md)**

### Quick Links
- **[Setup Guide](docs/SETUP.md)** - Development environment setup
- **[Architecture](docs/ARCHITECTURE.md)** - System design overview
- **[Testing Guide](docs/TESTING.md)** - Running tests
- **[Project Structure](docs/PROJECT_STRUCTURE.md)** - Codebase layout

### Feature Documentation
- **[Bulk Voucher Creation](docs/BULK_VOUCHER_CREATION.md)** - Bulk create vouchers by program
- **[Order Window Feature](docs/ORDER_WINDOW_FEATURE.md)** - Time-based ordering
- **[Combined Orders](docs/COMBINED_ORDER_FEATURE.md)** - Warehouse order consolidation
- **[Customer Numbers](docs/CUSTOMER_NUMBER_SYSTEM.md)** - Warehouse ID system
- **[Email System](docs/EMAIL_SYSTEM.md)** - Template management
- **[Logging System](docs/LOGGING_SYSTEM.md)** - Audit trails
- **[Signals & Automation](docs/SIGNALS_AUTOMATION.md)** - Automatic workflows

### Bug Fixes & Improvements
- **[Cart Bugs Fixed](docs/BUGS_FOUND.md)** - Edge case validations
- **[Cart Search Fix](docs/CART_SEARCH_BUG.md)** - Search filter fix
- **[CI/CD Setup](docs/CI_SETUP.md)** - Automated testing

## Quick Start

### Prerequisites
- Python 3.13+
- PostgreSQL (production) or SQLite (development)
- Node.js (for frontend tests)

### Installation

```bash
# Clone repository
git clone <repository-url>
cd basketful_app

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

Visit http://localhost:8000/admin/

### Running Tests

```bash
# Python tests
pytest

# JavaScript tests
npm test

# With coverage
pytest --cov=apps --cov-report=html
```

## Design Philosophy

Basketful is built with a **Lean and Human-Centered** mindset:

- ✅ **Automate repetitive work** for volunteers and staff
- ✅ **Surface only what matters** to reduce decision fatigue
- ✅ **Build accountability** and traceability into the system
- ✅ **Enforce business rules** (e.g., hygiene limits) at the model level
- ✅ **Provide flexibility** through admin-configurable features

## Key Features Highlight

### 🎯 Warehouse-Friendly
- Customer numbers with check digits (C-BKM-7)
- Print-optimized order views
- Combined orders for efficient picking

### 🔄 Automated Workflows
- Automatic account creation
- Auto-generated vouchers
- Balance recalculation on changes
- Email notifications

### 📊 Comprehensive Tracking
- Audit logging for all actions
- Email delivery tracking
- Order validation logs
- Voucher lifecycle tracking

### ⚙️ Admin Configurable
- Email templates (no code changes)
- Order window settings
- Voucher amounts and types
- Program schedules

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

See **[Testing Guide](docs/TESTING.md)** for running tests before submitting.

## License

This project is licensed under the terms specified in the LICENSE file.

## Maintainers & Contributors

Created and maintained by volunteers at **Love Your Neighbor** and the broader community.

### Special Thanks
- All contributors who have helped improve Basketful
- Community volunteers testing and providing feedback

---

📚 **For detailed documentation, see [docs/INDEX.md](docs/INDEX.md)**
