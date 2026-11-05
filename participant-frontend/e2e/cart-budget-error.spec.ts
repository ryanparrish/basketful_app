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
 *   2. That error names the specific problem (budget) and the amount over
 *      — not a bare "N issues found" count.
 *   3. Checkout is blocked until the cart is fixed.
 *
 * Fixture: `python manage.py seed_e2e_participant` creates participant
 * `e2e-participant` and product "E2E Over-Budget Test Item" priced at
 * $999.99, guaranteeing a 'balance' violation beyond any grace allowance.
 */
import { expect, test } from '@playwright/test';
import {
  OVER_BUDGET_PRICE,
  PRODUCTS,
  addToCart,
  cartMessage,
  checkoutButton,
  dollars,
  openCart,
  overBudgetBanner,
  readBalances,
} from './support/cart';

test('cart drawer explains a budget violation and blocks checkout', async ({ page }) => {
  await page.goto('/products');
  const balances = await readBalances(page);

  await addToCart(page, PRODUCTS.overBudgetFood);
  await openCart(page);

  const drawer = page.getByRole('dialog');
  const message = `Food balance exceeded by ${dollars(OVER_BUDGET_PRICE - balances.food)}`;
  // Shown once in the summary and again on the offending line itself
  // (validate-cart's product_ids), so the participant knows what to remove.
  await expect(drawer.getByText(message).first()).toBeVisible();
  await expect(drawer.locator('.MuiChip-label', { hasText: message })).toBeVisible();

  // The old behavior collapsed every error into a bare count with no
  // specifics — assert that generic phrasing is gone, not just that some
  // other text is present.
  await expect(page.getByText(/^\d+ issues? found in your cart$/i)).not.toBeVisible();

  await expect(checkoutButton(page)).toHaveText('Please fix cart errors');
  await expect(checkoutButton(page)).toBeDisabled();
  await expect(overBudgetBanner(page)).toBeVisible();
});

test('removing the over-budget item unblocks checkout', async ({ page }) => {
  await page.goto('/products');
  await addToCart(page, PRODUCTS.overBudgetFood);
  await openCart(page);
  await expect(cartMessage(page, /Food balance exceeded by/)).toBeVisible();

  await page.getByRole('button', { name: 'Remove from cart' }).click();
  await expect(page.getByText('Your cart is empty')).toBeVisible();

  // Click beside the drawer, as a participant would (the close button has
  // its own test below)
  await page.locator('.MuiBackdrop-root').click({ position: { x: 50, y: 300 } });
  await expect(page.getByText(/^Cart \(\d+\)$/)).toBeHidden();
  await addToCart(page, PRODUCTS.smallFood);
  await openCart(page);
  await expect(page.getByText(/balance exceeded/)).toHaveCount(0);
  await expect(checkoutButton(page)).toBeEnabled();
});

test('the cart drawer can be closed with its close button', async ({ page }) => {
  await page.goto('/products');
  await addToCart(page, PRODUCTS.smallFood);
  await openCart(page);

  // Fails fast instead of waiting out the test timeout when something
  // (like the app bar) sits on top of the button
  await page.getByRole('button', { name: 'Close cart' }).click({ timeout: 5_000 });
  await expect(page.getByText(/^Cart \(\d+\)$/)).toBeHidden();
});
