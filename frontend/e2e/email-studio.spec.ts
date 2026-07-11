/**
 * Email Design Studio — happy-path E2E.
 *
 * Requires a local Django backend on :8000 with a migrated dev DB and
 * an e2e superuser (see playwright.config.ts for the setup command).
 * Email uses the console backend in dev, so "Send test" is safe.
 */
import { expect, test, type Page } from '@playwright/test';

// Authentication happens once in auth.setup.ts (storageState) — the
// backend throttles logins at 5/minute.

const openOnboardingStudio = async (page: Page) => {
  await page.getByText('Email Types').click();
  await page.getByRole('cell', { name: 'New User Onboarding' }).click();
  await page.getByRole('link', { name: /edit/i }).first().click();
  await expect(page.getByTestId('studio-save')).toBeVisible({ timeout: 20_000 });
};

test.describe('Email Design Studio', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('Email Types')).toBeVisible({ timeout: 15_000 });
  });

  test('loads the studio with variables and preview', async ({ page }) => {
    await openOnboardingStudio(page);

    // Variables panel lists friendly labels from the registry.
    await expect(page.getByTestId('variables-panel')).toBeVisible();
    await expect(page.getByText("Recipient's username")).toBeVisible();

    // The live preview renders sample data, not raw {{ }} placeholders.
    const preview = page.frameLocator('iframe[title="Email Preview"]');
    await expect(preview.getByText('maria-hope').first()).toBeVisible({ timeout: 15_000 });
  });

  test('visual mode edits from a template preset and previews sample data', async ({ page }) => {
    await openOnboardingStudio(page);

    // Start from a preset — the canvas fills with the announcement layout.
    await page.getByRole('button', { name: 'Announcement' }).click();
    await expect(page.getByText('Write your announcement here.')).toBeVisible();

    // The preview compiles the design and substitutes sample values.
    const preview = page.frameLocator('iframe[title="Email Preview"]');
    await expect(preview.getByText(/Hi Maria/).first()).toBeVisible({ timeout: 15_000 });
  });

  test('code mode edit, save, and stale-design warning round trip', async ({ page }) => {
    await openOnboardingStudio(page);

    // Give this language a design first (visual save).
    await page.getByRole('button', { name: 'Simple notice' }).click();
    await page.getByTestId('studio-save').click();
    await expect(page.getByText(/Saved English content/i)).toBeVisible();

    // Switch to code mode — Monaco shows the compiled HTML.
    await page.getByTestId('mode-code').click();
    await expect(page.locator('.monaco-editor').first()).toBeVisible({ timeout: 20_000 });

    // Edit the HTML via Monaco and save — confirm dialog warns about
    // disconnecting the design.
    await page.locator('.monaco-editor').first().click();
    await page.keyboard.press('ControlOrMeta+a');
    await page.keyboard.type('<p>Code edited for {{ user.first_name }}</p>');
    await page.getByTestId('studio-save').click();
    await expect(page.getByText('Save code edits?')).toBeVisible();
    await page.getByRole('button', { name: 'Save code edits' }).click();
    await expect(page.getByText(/Saved English content/i)).toBeVisible();

    // Returning to Visual shows the stale-design warning.
    await page.getByTestId('mode-visual').click();
    await expect(page.getByTestId('stale-design-warning')).toBeVisible();
  });

  test('spanish tab is independent and send test succeeds', async ({ page }) => {
    await openOnboardingStudio(page);

    await page.getByRole('tab', { name: 'Español' }).click();
    await expect(page.getByText(/falls back to English/i)).toBeVisible();

    // Send a test email (console backend in dev) — success toast.
    await page.getByRole('button', { name: 'Send test' }).click();
    await expect(page.getByText(/Test email sent to/i)).toBeVisible({ timeout: 15_000 });
  });
});
