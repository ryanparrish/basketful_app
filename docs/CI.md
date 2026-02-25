# CI/CD (GitHub Actions)

> Last updated: February 2026

This document describes the continuous integration setup for the Basketful project.

## Workflow Files

- `.github/workflows/ci.yml` - Backend tests and backend Docker image
- `.github/workflows/frontend-ci.yml` - React frontend build checks and frontend Docker images

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

## Frontend Container Pipeline

The frontend workflow builds and validates:

- `frontend` (admin React app)
- `participant-frontend` (participant React app)

Current build checks:

- Admin: `npm run build`
- Participant: `npx vite build`

On `push` to `main`, `develop`, or git tags like `v1.2.3`, it also builds and pushes:

- `${DOCKER_USERNAME}/basketful-admin`
- `${DOCKER_USERNAME}/basketful-participant`

Frontend image tag strategy:

- `develop` pushes: publishes `latest` (staging)
- `vX.Y.Z` tag pushes: publishes version tag `X.Y.Z` and `prod-latest`
- branch and sha tags are also published for traceability

Admin base path strategy in CI:

- `develop` builds: `VITE_BASE_PATH=/new/admin/`
- `main` and release tag builds: `VITE_BASE_PATH=/admin/`

### Required GitHub Secrets

- `DOCKER_USERNAME`
- `DOCKER_PASSWORD`
