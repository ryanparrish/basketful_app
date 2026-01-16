# Testing

Run the full test suite with coverage:

```bash
.venv/bin/python -m pytest --cov=apps --cov-report=xml --cov-report=html
```

Quick test run (single file):

```bash
.venv/bin/python -m pytest apps/account/tests/test_account_balance.py -v
```

Notes about environment for tests:
- `DJANGO_SETTINGS_MODULE` is set in `pytest.ini` to `core.settings`.
- CI provides environment variables such as `DATABASE_URL`, `SECRET_KEY`, `DOMAIN_NAME`, and `HASHIDS_SALT`.
- Tests use defaults for reCAPTCHA and some other keys during CI/local runs to avoid requiring production secrets.

CI: see `docs/CI.md` for workflow variables and tips.