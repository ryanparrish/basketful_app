/**
 * Places real orders through the deployed React cart, end to end: the cart
 * says checkout is open, and POST /api/v1/orders/ agrees.
 *
 * A participant may only have one open order, and an open order makes
 * every later cart validation fail, so this file runs in its own
 * Playwright project after every other spec, one test at a time, and
 * cancels the order after each test by re-running the seed command.
 */
import { expect, test, type Page } from '@playwright/test';
import { PRODUCTS, addToCart, checkoutButton, openCart } from './support/cart';
import { seedE2eParticipant } from './support/seed';

test.describe.configure({ mode: 'serial' });

test.afterEach(() => {
  seedE2eParticipant();
});

async function submitOrder(page: Page) {
  await openCart(page);
  await expect(checkoutButton(page)).toBeEnabled();
  await checkoutButton(page).click();
  await expect(page).toHaveURL(/\/checkout$/);

  await page.getByRole('button', { name: 'Submit Order' }).click();
  await expect(page.getByText('Order Placed!')).toBeVisible({ timeout: 15_000 });
}

test('a cart of food, hygiene and Go Fresh within every balance places an order', async ({ page }) => {
  await page.goto('/products');
  await addToCart(page, PRODUCTS.smallFood);
  await addToCart(page, PRODUCTS.smallHygiene);
  await addToCart(page, PRODUCTS.smallGoFresh);

  await submitOrder(page);
});

test('a cart over the food balance by less than the grace amount places an order', async ({ page }) => {
  await page.goto('/products');
  await addToCart(page, PRODUCTS.graceFood);

  await submitOrder(page);
});
