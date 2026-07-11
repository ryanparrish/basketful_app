/**
 * One-time authentication for the e2e suite.
 *
 * Logs in through the real UI once and saves the session (cookie JWT)
 * to storageState for every spec to reuse — the backend throttles the
 * login endpoint at 5/minute, so per-test logins are both slow and
 * flaky.
 */
import { expect, test as setup } from '@playwright/test';

const E2E_USERNAME = process.env.E2E_ADMIN_USERNAME || 'e2e-admin';
const E2E_PASSWORD = process.env.E2E_ADMIN_PASSWORD || 'e2e-password';

export const STORAGE_STATE = 'e2e/.auth/state.json';

setup('authenticate', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Username').fill(E2E_USERNAME);
  await page.getByLabel('Password').fill(E2E_PASSWORD);
  // Dev uses Google's reCAPTCHA test keys — the checkbox always passes.
  await page
    .frameLocator('iframe[title="reCAPTCHA"]')
    .locator('#recaptcha-anchor')
    .click();
  const signIn = page.getByRole('button', { name: /sign in|login/i });
  await expect(signIn).toBeEnabled({ timeout: 15_000 });
  await signIn.click();
  await expect(page.getByText('Email Types')).toBeVisible({ timeout: 15_000 });
  await page.context().storageState({ path: STORAGE_STATE });
});
