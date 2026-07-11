/**
 * Playwright E2E configuration for the admin frontend.
 *
 * Precondition: a local Django backend on :8000 with a migrated dev DB
 * and an e2e superuser (credentials overridable via E2E_ADMIN_USERNAME /
 * E2E_ADMIN_PASSWORD):
 *
 *   source .venv/bin/activate && python manage.py migrate
 *   python manage.py shell -c "
 *   from django.contrib.auth import get_user_model; U = get_user_model()
 *   u, _ = U.objects.get_or_create(username='e2e-admin', defaults={'email': 'e2e-admin@example.com'})
 *   u.is_staff = u.is_superuser = True; u.set_password('e2e-password'); u.save()"
 *   python manage.py runserver
 *
 * Celery is eager and email uses the console backend in dev, so the
 * studio's "Send test" is safe to exercise. The vite dev server is
 * started automatically.
 */
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  // Serial: the specs mutate the same email template.
  workers: 1,
  fullyParallel: false,
  use: {
    baseURL: 'http://localhost:5174',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'setup', testMatch: /auth\.setup\.ts/ },
    {
      name: 'chromium',
      use: { storageState: 'e2e/.auth/state.json' },
      dependencies: ['setup'],
    },
  ],
  webServer: {
    command: 'npm run dev',
    port: 5174,
    reuseExistingServer: !process.env.CI,
  },
});
