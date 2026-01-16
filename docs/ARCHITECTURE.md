# Architecture Overview

This Django project follows a modular app layout. High-level apps of interest:

- `apps/account` — account and balance models
- `apps/pantry` — product/catalog, categories, mobile-first ordering UI
- `apps/orders` — order models, voucher consumption, order validation
- `apps/voucher` — voucher models and validation
- `apps/log` — logging, order validation logs
- `core` — project settings, middleware, celery, and app wiring

Important notes:
- Mobile UI: `apps/pantry/templates/food_orders/create_order.html` contains the ordering interface and JS enhancements.
- Voucher consumption logic and validation are in `apps/orders/models.py`.
- Email sending uses Mailgun via `django-anymail` in production.

Migrations live under each app's `migrations/` directory. Tests are under each app's `tests/` directory and use `pytest-django`.

If you want an ER diagram or class-level diagrams, I can generate them next.