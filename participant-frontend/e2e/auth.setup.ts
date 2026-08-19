/**
 * One-time authentication for the e2e suite.
 *
 * Logs in through the real UI once and saves the session (cookie JWT)
 * to storageState for every spec to reuse.
 */
import { expect, test as setup } from '@playwright/test';

const E2E_USERNAME = process.env.E2E_PARTICIPANT_USERNAME || 'e2e-participant';
const E2E_PASSWORD = process.env.E2E_PARTICIPANT_PASSWORD || 'e2e-password';

export const STORAGE_STATE = 'e2e/.auth/state.json';

setup('authenticate', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Username or Customer Number').fill(E2E_USERNAME);
  await page.getByLabel('Password', { exact: true }).fill(E2E_PASSWORD);
  // Dev uses Google's reCAPTCHA test keys — the checkbox always passes.
  await page
    .frameLocator('iframe[title="reCAPTCHA"]')
    .locator('#recaptcha-anchor')
    .click();
  const signIn = page.getByRole('button', { name: /sign in/i });
  await expect(signIn).toBeEnabled({ timeout: 15_000 });
  await signIn.click();
  await expect(page).toHaveURL(/\/products/, { timeout: 15_000 });
  await page.context().storageState({ path: STORAGE_STATE });
});
