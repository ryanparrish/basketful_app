# CI/CD (GitHub Actions)

> Last updated: 2026-07-13

This document describes the continuous integration setup for the Basketful project.

## Workflow Files

- `.github/workflows/ci.yml` — Backend tests/lint and backend Docker image (job names: `test`, `docker`)
- `.github/workflows/frontend-ci.yml` — React frontend build/test checks and frontend Docker images (job names: `frontend-build-check`, `frontend-docker`)
- `.github/workflows/mutation-testing.yml` — Scheduled/on-demand mutmut mutation testing (not a merge gate)
- `.github/workflows/render-diagrams.yml` — Renders `docs/diagrams/*.mmd` to PNGs and commits them back to the repo

## Services

The `ci.yml` `test` job and `mutation-testing.yml` jobs use these service containers:

| Service | Version | Purpose |
|---------|---------|---------|
| PostgreSQL | 15 | Test database (`basketful_test`) |
| Redis | 7 | Celery broker for tests |

## Environment Variables

### Backend job (`ci.yml` → `test`)

All of these are set inline in the workflow's `env:` blocks (not GitHub secrets), except where noted:

| Variable | Value in CI | Notes |
|----------|-------------|-------|
| `DJANGO_SETTINGS_MODULE` | `core.settings` | |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/basketful_test` | Matches the `postgres` service container |
| `REDIS_URL` | `redis://localhost:6379/0` | Matches the `redis` service container |
| `SECRET_KEY` | `test-secret-key-for-ci` | Required by `core/settings.py`, no default |
| `DOMAIN_NAME` | `test.example.com` | |
| `HASHIDS_SALT` | `test-hashids-salt-for-ci` | Required by `core/settings.py`, no default |
| `DEBUG` | `'True'` | |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | |
| `CELERY_TASK_ALWAYS_EAGER` | `'True'` | Also auto-forced by `core/settings.py` whenever `pytest` is detected, so this is belt-and-suspenders |
| `MAILGUN_API_KEY` | `test-key` | Only read in the "Run tests" / coverage steps, not the migrate step |
| `MAILGUN_SENDER_DOMAIN` | `test.example.com` | |
| `DEFAULT_FROM_EMAIL` | `test@example.com` | |

### Required GitHub Secrets

| Secret | Used by |
|--------|---------|
| `CODECOV_TOKEN` | `ci.yml` — upload coverage to Codecov (job continues even if this fails: `fail_ci_if_error: false`) |
| `DOCKER_USERNAME` | `ci.yml` (`docker` job) and `frontend-ci.yml` (`frontend-docker` job) — Docker Hub login and image namespace |
| `DOCKER_PASSWORD` | Same as above |

## Backend Pipeline Steps (`ci.yml` → `test`)

1. **Checkout**
2. **Set up Python 3.13** (`cache: pip`)
3. **Install dependencies** — `pip install -r requirements.txt`
4. **Set up Node.js 18** — for Mermaid validation only
5. **Validate Mermaid diagrams** — renders every `docs/diagrams/*.mmd` with `@mermaid-js/mermaid-cli`; `continue-on-error: true` (never fails the job)
6. **Run flake8** — `flake8 apps/ core/ --count --show-source --statistics` (this one is NOT `continue-on-error`; a lint failure fails the job)
7. **Compile translation catalogs** — installs `gettext`, runs `msgfmt --check` against `locale/es/LC_MESSAGES/django.po`, then `django-admin compilemessages -l es ...` (mirrors the `Dockerfile` build step)
8. **Run migrations** — `python manage.py migrate --noinput`
9. **Run tests** — `pytest --tb=short --maxfail=5 -v`
10. **Generate coverage report** (`if: always()`) — separate `pytest --cov=apps --cov-report=xml --cov-report=html --cov-report=term-missing` invocation
11. **Print coverage summary** (`if: always()`) — `coverage report --skip-covered --sort=cover` and `coverage report --skip-empty`
12. **Upload coverage reports** — `htmlcov/` and `coverage.xml` as a build artifact
13. **Upload coverage to Codecov** — `codecov/codecov-action@v4`, `fail_ci_if_error: false`

A second job, **`docker`**, runs only `if: github.event_name == 'push' && (main || develop)` and only `needs: test`. It builds and pushes the backend image to Docker Hub as `${DOCKER_USERNAME}/basketful:<branch>` and `${DOCKER_USERNAME}/basketful:latest` (registry-cached via `type=registry` buildx cache).

## Triggers

- `ci.yml`: `push` and `pull_request` on `main` and `develop`.
- `frontend-ci.yml`: `push`/`pull_request` on `main`/`develop`, plus `push` on tags `v*`. Pull requests are additionally scoped with `paths:` to `frontend/**`, `participant-frontend/**`, and the workflow file itself.

## Troubleshooting

### Missing Environment Variables

If CI fails with missing variable errors:

1. Check if the variable is defined in the workflow's `env:` block.
2. Add to GitHub repository secrets for sensitive values (Docker/Codecov credentials — see above).
3. Use the workflow-level `env:` block for non-sensitive values, matching the pattern already used in `ci.yml`.

### Celery Connection Errors

If tests fail with "Error connecting to broker":

1. `CELERY_TASK_ALWAYS_EAGER` is already forced to `True` under pytest by `core/settings.py` itself — this should not normally happen in CI.
2. Locally, either run Redis or set `CELERY_TASK_ALWAYS_EAGER=True` in your `.env` (see [SETUP.md](SETUP.md)).

### Database Connection Issues

The `postgres` service container already has a healthcheck:

```yaml
options: >-
  --health-cmd pg_isready
  --health-interval 10s
  --health-timeout 5s
  --health-retries 5
```

## Local CI Simulation

Run the closest local equivalent of the backend job:

```bash
# Lint (exact command CI runs)
flake8 apps/ core/ --count --show-source --statistics

# Migrations
python manage.py migrate --noinput

# Tests with coverage (exact command CI runs)
pytest --cov=apps --cov-report=xml --cov-report=term-missing
```

Note: `python manage.py makemigrations --check --dry-run` is a good local habit before committing model changes, but it is **not currently a step in `ci.yml`** — nothing blocks a PR today if a migration is missing.

## Mutation Testing (`mutation-testing.yml`)

Runs `mutmut` against a fixed set of targets — not part of the merge-blocking pipeline.

- **Triggers**: scheduled every Sunday at 02:00 UTC (`workflow_dispatch` also available, with an optional `paths` input to mutate specific files instead of the defaults).
- **Default matrix** (`mutation-test-default` job, runs when no custom `paths` given): `apps/orders/models.py`, `apps/orders/utils/order_utils.py`, `apps/account/models.py`, each tested against its own app's `tests/` directory.
- **Custom run** (`mutation-test-custom` job, runs only when `workflow_dispatch` supplies `paths`): mutates the given comma-separated paths against the full `apps/` test suite.
- Uses Python 3.11 (not 3.13) and `pip install "mutmut<3" pytest-django`.
- Uploads `htmlmut/`, `mutation-results.txt`, and `.mutmut-cache` as artifacts (90-day retention) and writes a score summary to the job summary (`$GITHUB_STEP_SUMMARY`).

## Render Diagrams (`render-diagrams.yml`)

- **Trigger**: `push` to any branch (`main`, `develop`, or `**`).
- Installs `@mermaid-js/mermaid-cli`, runs `scripts/render_diagrams.sh` to render `docs/diagrams/*.mmd` to PNGs, then commits any changed images under `docs/diagrams/images` back to the branch as the `github-actions[bot]` user (`permissions: contents: write`).
- This is separate from the "Validate Mermaid diagrams" step inside `ci.yml`, which only checks that the `.mmd` files render without error and does not commit anything.

## Related Documentation

- [TESTING.md](TESTING.md) — Test commands and organization
- [SETUP.md](SETUP.md) — Development environment setup

## Frontend Pipeline (`frontend-ci.yml`)

### `frontend-build-check` (matrix: `admin` / `participant`)

1. Checkout, setup Node 20 (`cache-dependency-path` per app's `package-lock.json`)
2. `npm ci` in the app's working directory
3. **Run tests** — `npx vitest run` (this runs for both apps; there is no longer a gap here — vitest tests block the build)
4. **Build** — admin: `npm run build`; participant: `npx vite build`. `VITE_BASE_PATH` is set to `/new/admin/` for admin and `/new/cart/` for participant during this build-check step, regardless of branch.

### `frontend-docker` (needs `frontend-build-check`; only on push to `main`, `develop`, or a `v*` tag)

Builds and pushes both frontend Docker images with build args `VITE_API_URL=/api/v1` and `VITE_BASE_PATH` — **fixed to `/new/admin/` (admin) and `/new/cart/` (participant) for every branch and tag**, not varied by branch. (These base paths match the real production nginx routing in `nginx/conf.d/basketful.conf` — see [DEPLOYMENT.md](DEPLOYMENT.md).)

Docker Hub image names:

- `${DOCKER_USERNAME}/basketful-admin`
- `${DOCKER_USERNAME}/basketful-participant`

Tag strategy (via `docker/metadata-action`), which differs by branch/tag:

- Push to `main`: tags `main`, `sha-<short>`, and `latest`
- Push to `develop`: tags `develop`, `sha-<short>`, and `develop-latest`
- Push of tag `vX.Y.Z`: tags `X.Y.Z`, `sha-<short>`, and `prod-latest`

### Required GitHub Secrets

- `DOCKER_USERNAME`
- `DOCKER_PASSWORD`
