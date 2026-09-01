# Setup — Local Development

> Last updated: 2026-07-13

1. Create virtualenv and install dependencies (Python 3.13 — matches `Dockerfile` and CI):

```bash
python -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

2. Create a `.env` file in the project root (read by `core/settings.py` via `django-environ`). These have **no default** and Django will raise `ImproperlyConfigured` at startup (including for `pytest`) if they're missing:

- `SECRET_KEY` (required)
- `DATABASE_URL` (required — no sqlite fallback; e.g. `postgres://basketful:basketful@localhost:5432/basketful` against a local/shared Postgres instance per the project's migration policy)
- `HASHIDS_SALT` (required — any string; used to generate customer numbers, no test default is auto-provided by conftest, so tests will fail without it)

Variables with defaults you can usually leave unset for local dev:

- `DOMAIN_NAME` (defaults to `localhost`)
- `DJANGO_ENV` (defaults to `dev`; set to `prod` to switch on Mailgun email backend, `ALLOWED_HOSTS` enforcement, and secure cookies)
- `DEBUG` (defaults to `False` — set `DEBUG=True` in `.env` for local development)
- `RECAPTCHA_PUBLIC_KEY` / `RECAPTCHA_PRIVATE_KEY` (default to Google's published test keys)
- `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` (default to `redis://localhost:6379/0` — run Redis locally, or set `CELERY_TASK_ALWAYS_EAGER=True` to run Celery tasks synchronously without a broker; this is forced on automatically under `pytest`)

3. Run migrations and create a superuser:

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver
```

Visit http://localhost:8000/admin/ (Django admin) or http://localhost:8000/api/ (DRF API root).

4. Frontend setup (two separate React/Vite apps, each with its own `package.json`):

```bash
# Admin frontend (staff dashboard) — react-admin, served at /admin/ in dev
cd frontend
npm ci
npm run dev

# Participant frontend (shopping portal) — Refine + MUI, served at /
cd ../participant-frontend
npm ci
npm run dev
```

Both dev servers default to Vite ports in `5173`–`5175`, which are already present in `CORS_ALLOWED_ORIGINS`'s default list in `core/settings.py`.

5. Root-level JS tests (Jest, for the vanilla JS under `apps/*/static/js/`, e.g. cart logic) use the top-level `package.json`:

```bash
npm ci
npm test
```

This is separate from the frontend apps' own test runners (Vitest) — see `docs/TESTING.md`.

6. Notes:
- For email testing the project uses the console backend locally (`EMAIL_BACKEND` defaults to Django's console backend unless `DJANGO_ENV=prod`).
- For production, set `DJANGO_ENV=prod` and provide `MAILGUN_API_KEY`, `MAILGUN_SENDER_DOMAIN`, and `DEFAULT_FROM_EMAIL` — production email always goes through `django-anymail`'s Mailgun backend (SMTP settings are not read).
- Translation catalogs (`locale/es/LC_MESSAGES/django.po`) must be compiled with `django-admin compilemessages -l es` before Spanish strings will render (see `Dockerfile` and `.github/workflows/ci.yml` for the exact invocation); this requires `gettext` installed locally.