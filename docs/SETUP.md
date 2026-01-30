# Setup — Local Development

> Last updated: January 2026

1. Create virtualenv and install dependencies:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

2. Create a `.env` file in the project root or export environment variables. Minimal variables for local dev/tests:

- `SECRET_KEY` (required)
- `DATABASE_URL` (defaults to sqlite if not provided)
- `DOMAIN_NAME` (defaults to `localhost`)
- `HASHIDS_SALT` (a string; test default provided)

3. Run migrations and create a superuser:

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver
```

4. Notes:
- For email testing the project uses console backend locally.
- For production, set `ENVIRONMENT=prod` and provide `MAILGUN_API_KEY`, `MAILGUN_SENDER_DOMAIN`, and real `DEFAULT_FROM_EMAIL`.