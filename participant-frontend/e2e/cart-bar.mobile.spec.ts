/**
 * Story: on a phone, a participant can always see what's left in their
 * balances and get to their cart.
 *
 * Regression guard: after the Refine migration the phone layout lost its
 * bottom navigation, and with it every way into the cart — the header hid
 * its cart icon on mobile and the sider renders nothing there. Nobody
 * noticed until a participant reported it. This runs in the `mobile`
 * Playwright project (Pixel 7 viewport).
 *
 * Fixture: `python manage.py seed_e2e_participant` (see playwright.config.ts).
 */
import { expect, test } from '@playwright/test';

test('phone layout shows the cart bar with balances and opens the cart', async ({ page }) => {
  await page.goto('/products');

  const bar = page.getByRole('region', { name: 'Cart summary' });
  await expect(bar).toBeVisible();
  await expect(bar.getByText(/Food left: \$\d/)).toBeVisible();
  await expect(bar.getByText(/Hygiene left: \$\d/)).toBeVisible();

  await page.getByRole('button', { name: 'Add to cart' }).first().click();
  await expect(bar.getByText(/^Cart \(1\)/)).toBeVisible();

  await bar.getByRole('button', { name: /view cart/i }).click();
  await expect(page.getByText(/^Cart \(1\)$/)).toBeVisible();
  // The drawer header (title + close) must not be hidden under the app bar.
  // click() fails if another element (the AppBar) is on top of the button,
  // which toBeInViewport() alone would not catch.
  await page.getByRole('button', { name: 'Close cart' }).click({ timeout: 5_000 });
  await expect(page.getByRole('button', { name: 'Close cart' })).toBeHidden();
});

test('header cart icon is also available on phones', async ({ page }) => {
  await page.goto('/products');
  await expect(page.getByRole('button', { name: 'Open cart' })).toBeVisible();
});
