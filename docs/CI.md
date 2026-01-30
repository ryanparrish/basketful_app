# CI/CD (GitHub Actions)

> Last updated: January 2026

This document describes the continuous integration setup for the Basketful project.

## Workflow File

**Location:** `.github/workflows/ci.yml`

## Services

The CI pipeline uses these service containers:

| Service | Version | Purpose |
|---------|---------|---------|
| PostgreSQL | 15 | Test database |
| Redis | 7 | Celery broker (for integration tests) |

## Environment Variables

### Required in CI

| Variable | Example | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `postgres://user:pass@localhost/test_db` | Set automatically from postgres service |
| `SECRET_KEY` | `test-secret-key` | Use GitHub secrets for production |
| `DOMAIN_NAME` | `test.example.com` | Test domain |
| `HASHIDS_SALT` | `test-salt` | For URL encoding |
| `DJANGO_SETTINGS_MODULE` | `core.settings` | Django settings |

### Email Configuration

| Variable | Purpose |
|----------|---------|
| `MAILGUN_API_KEY` | Mailgun API authentication |
| `MAILGUN_SENDER_DOMAIN` | Sending domain |
| `DEFAULT_FROM_EMAIL` | Default sender address |

### Celery Configuration

```yaml
CELERY_TASK_ALWAYS_EAGER: true
```

This runs Celery tasks synchronously in tests, avoiding broker connection issues.

## Pipeline Steps

1. **Checkout** — Clone repository
2. **Setup Python** — Install Python 3.x
3. **Install Dependencies** — `pip install -r requirements.txt`
4. **Run Migrations** — `python manage.py migrate`
5. **Run Tests** — `pytest --cov=apps`
6. **Upload Coverage** — Send to coverage service

## Troubleshooting

### Missing Environment Variables

If CI fails with missing variable errors:

1. Check if variable is defined in workflow
2. Add to GitHub repository secrets for sensitive values
3. Use workflow-level `env:` block for non-sensitive values

### Celery Connection Errors

If tests fail with "Error connecting to broker":

1. Ensure `CELERY_TASK_ALWAYS_EAGER=true` is set
2. Mock Celery task delays in fixtures (see [TESTING.md](TESTING.md))

### Database Connection Issues

PostgreSQL service may need extra time to start. The workflow should include:

```yaml
options: >-
  --health-cmd pg_isready
  --health-interval 10s
  --health-timeout 5s
  --health-retries 5
```

## Local CI Simulation

Run the same checks locally:

```bash
# Lint
flake8 apps/ core/

# Tests with coverage
pytest --cov=apps --cov-report=xml

# Check migrations
python manage.py makemigrations --check --dry-run
```

## Related Documentation

- [TESTING.md](TESTING.md) — Test commands and organization
- [SETUP.md](SETUP.md) — Development environment setup