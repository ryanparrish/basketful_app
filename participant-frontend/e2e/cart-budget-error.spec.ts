/**
 * Story (issue #98 — "Errors in new cart"):
 *
 *   As a participant shopping in the new cart, when I add an item I can't
 *   afford, I want the cart to tell me specifically why it's blocked (e.g.
 *   "over budget by $X.XX") — not just that "an issue" exists — so I know
 *   what to remove or change to check out.
 *
 * Acceptance criteria:
 *   1. Adding an over-budget item shows a validation error in the cart
 *      drawer, the very first place a participant sees feedback.
 *   2. That error names the specific problem (budget) and, ideally, the
 *      amount over — not a bare "N issues found" count.
 *
 * Fixture: `python manage.py seed_e2e_participant` creates participant
 * `e2e-participant` with a $100 balance and product "E2E Over-Budget Test
 * Item" priced at $999.99, guaranteeing a 'balance' violation regardless of
 * VoucherSetting configuration.
 */
import { expect, test } from '@playwright/test';

const OVER_BUDGET_PRODUCT = 'E2E Over-Budget Test Item';

test('cart drawer explains a budget violation instead of a bare issue count', async ({ page }) => {
  await page.goto('/products');

  await page.getByPlaceholder('Search products...').fill(OVER_BUDGET_PRODUCT);
  await page.getByRole('button', { name: 'Add to cart' }).click();

  // Backend validation is debounced 500ms after the cart changes.
  await page.getByTestId('ShoppingCartIcon').locator('..').click();
  await expect(page.getByText(/^Cart \(\d+\)$/)).toBeVisible();

  await expect(page.getByText(/exceeded by \$\d/i)).toBeVisible({ timeout: 10_000 });

  // The old behavior collapsed every error into a bare count with no
  // specifics — assert that generic phrasing is gone, not just that some
  // other text is present.
  await expect(page.getByText(/^\d+ issues? found in your cart$/i)).not.toBeVisible();
});
