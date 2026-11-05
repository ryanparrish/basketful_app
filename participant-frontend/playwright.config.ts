/**
 * Playwright E2E configuration for the participant frontend.
 *
 * Precondition: a local Django backend on :8000 with a migrated dev DB,
 * started with a raised per-user rate limit (every spec signs in as the
 * same participant, and the default 100/minute throttles the suite):
 *
 *   DRF_USER_THROTTLE_RATE=2000/minute python manage.py runserver
 *
 * global-setup runs `python manage.py seed_e2e_participant` (the repo's
 * .venv Python, or E2E_PYTHON; set E2E_SKIP_SEED=1 to skip it). That
 * command creates participant user `e2e-participant` / `e2e-password`,
 * products priced against each of its balances (food, Hygiene, Go Fresh,
 * and just inside the grace allowance), and cancels its open orders.
 *
 * Celery is eager and reCAPTCHA uses Google's always-passing test keys in
 * dev, so login through the real UI is safe to exercise per spec run.
 */
import { defineConfig, devices } from '@playwright/test';

const PLACES_ORDERS = /checkout-place-order\.spec\.ts/;

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  globalSetup: './e2e/global-setup.ts',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'setup',
      testMatch: /auth\.setup\.ts/,
      testIgnore: /legacy\//,
      teardown: 'place-order',
    },
    {
      name: 'chromium',
      use: { storageState: 'e2e/.auth/state.json' },
      dependencies: ['setup'],
      testIgnore: [/legacy\//, /\.mobile\.spec\.ts$/, PLACES_ORDERS],
    },
    // Phone-sized viewport: the layout switches (no sider, bottom cart bar)
    // below the md breakpoint, so mobile-only regressions need their own run.
    {
      name: 'mobile',
      use: { ...devices['Pixel 7'], storageState: 'e2e/.auth/state.json' },
      dependencies: ['setup'],
      testMatch: /\.mobile\.spec\.ts$/,
    },
    // A placed order makes every later cart validation fail until it is
    // cancelled, so the specs that place orders run as setup's teardown:
    // after every other spec, whether or not those passed.
    {
      name: 'place-order',
      use: { storageState: 'e2e/.auth/state.json' },
      testMatch: PLACES_ORDERS,
    },
    // Regression tests against the legacy Django-rendered site, which the
    // React cart above replaced. These log in via the plain Django form
    // directly, so they skip the React auth.setup/storageState chain and
    // hit :8000 with absolute URLs.
    {
      name: 'legacy',
      testDir: './e2e/legacy',
    },
  ],
  webServer: {
    command: 'npm run dev',
    port: 5173,
    reuseExistingServer: !process.env.CI,
  },
});
