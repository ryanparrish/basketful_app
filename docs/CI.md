# CI (GitHub Actions)

Workflow: `.github/workflows/ci.yml`

Key points:
- Uses `postgres:15` and `redis:7` services for tests.
- Sets `DJANGO_SETTINGS_MODULE=core.settings` in runners.
- Important env vars provided in CI steps:
  - `DATABASE_URL` (postgres://...)
  - `SECRET_KEY`
  - `DOMAIN_NAME` (test.example.com)
  - `HASHIDS_SALT`
  - `MAILGUN_API_KEY`, `MAILGUN_SENDER_DOMAIN`, `DEFAULT_FROM_EMAIL` for mail-related tests
  - `CELERY_TASK_ALWAYS_EAGER=true` for synchronous Celery tasks in tests

If CI fails due to missing env vars, add them to the workflow or a repository secret. For sensitive values use GitHub Actions secrets rather than hardcoding.
