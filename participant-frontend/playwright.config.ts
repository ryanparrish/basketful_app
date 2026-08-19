/**
 * Playwright E2E configuration for the participant frontend.
 *
 * Precondition: a local Django backend on :8000 with a migrated dev DB,
 * plus the deterministic e2e fixture:
 *
 *   source .venv/bin/activate && python manage.py migrate
 *   python manage.py seed_e2e_participant
 *
 * That command creates participant user `e2e-participant` / `e2e-password`
 * with a $100 balance, and an "E2E Over-Budget Test Item" product priced at
 * $999.99 — guaranteed to exceed any participant's budget regardless of
 * VoucherSetting configuration.
 *
 * Celery is eager and reCAPTCHA uses Google's always-passing test keys in
 * dev, so login through the real UI is safe to exercise per spec run.
 */
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: 'http://localhost:5173',
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
    port: 5173,
    reuseExistingServer: !process.env.CI,
  },
});
