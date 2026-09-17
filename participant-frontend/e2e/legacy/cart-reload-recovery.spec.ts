/**
 * Regression coverage for the legacy "original-site" Django-rendered cart
 * (apps/pantry/views.py, apps/orders/views.py, core/templates/pantry/create_order.html,
 * apps/pantry/static/js/cart.js) — this is the cart participants actually
 * use; participant-frontend's React cart is not deployed.
 *
 * Story: multiple participants reported that after logging back in and
 * building a cart, scrolling back up to review it erased everything, then
 * submitting kicked them out of checkout partway through.
 *
 * Root cause: commit c23d6a7 changed initializeCart() to unconditionally
 * trust the server's session cart, including when it's `{}`. "Add to Cart"
 * only mutated an in-memory JS object + localStorage; the session cart was
 * written server-side exactly once, inside submitOrder()'s POST to
 * /update-cart/. Any reload of /create-order/ before Submit was clicked
 * (e.g. a mobile pull-to-refresh gesture while scrolling back up to check
 * the cart) re-embedded the still-empty session cart and wiped the
 * in-progress cart — which then made review_order()/submit_order()
 * (apps/orders/views.py) bounce straight back to create_order, the
 * "kicked out mid-checkout" experience.
 *
 * Fix: apps/pantry/static/js/cart.js now (a) syncs every add/remove to the
 * server immediately instead of only at Submit, and (b) falls back to a
 * recent local cart — scoped to a per-session token so a shared/kiosk
 * device can't inherit another participant's leftovers, and capped at
 * CART_TTL_MS (30 min) — when the session cart looks empty. This suite
 * verifies the fix end-to-end: a cart survives a bare reload, and a
 * sufficiently old one does not resurrect.
 *
 * Fixture: `python manage.py seed_e2e_participant` (same fixture the React
 * e2e suite uses) creates participant `e2e-participant` / `e2e-password`
 * plus product "E2E Over-Budget Test Item" — price is irrelevant here since
 * this cart never runs balance validation client-side.
 *
 * Precondition: a local Django backend on :8000 with a migrated dev DB and
 * the fixture above seeded. This suite talks to the Django-rendered legacy
 * site directly and does not go through the React app or its auth setup.
 */
import { expect, test } from '@playwright/test';

const BASE_URL = 'http://localhost:8000';
const E2E_USERNAME = process.env.E2E_PARTICIPANT_USERNAME || 'e2e-participant';
const E2E_PASSWORD = process.env.E2E_PARTICIPANT_PASSWORD || 'e2e-password';
const PRODUCT_NAME = 'E2E Over-Budget Test Item';
const CART_TTL_MS = 30 * 60 * 1000;

async function login(page) {
  await page.goto(`${BASE_URL}/login/`);
  await page.fill('#id_username', E2E_USERNAME);
  await page.fill('#id_password', E2E_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`${BASE_URL}/dashboard/`);
}

async function addProductToCartWithoutSubmitting(page) {
  const productCard = page.locator('.card', { hasText: PRODUCT_NAME });
  await productCard.locator('input.quantity-input').fill('1');
  await productCard.locator('.add-to-cart').click();

  await page.click('#cart-drawer-toggle');
  await expect(page.locator('#mobile-cart-items')).toContainText(PRODUCT_NAME);
}

test('a reload before Submit no longer wipes the in-progress cart', async ({ page }) => {
  await login(page);
  await page.goto(`${BASE_URL}/create-order/`);
  await addProductToCartWithoutSubmitting(page);

  // Simulate what a pull-to-refresh / backgrounded-tab reload does: a
  // plain full page reload, with Submit never having been clicked.
  await page.reload();

  await page.click('#cart-drawer-toggle');
  const cartItemsText = await page.locator('#mobile-cart-items').innerText();
  expect(cartItemsText).toContain(PRODUCT_NAME);

  // The recovered cart re-syncs to the server, so checkout no longer
  // bounces back to create-order the way it did before the fix.
  await page.goto(`${BASE_URL}/review-order/`);
  await expect(page).toHaveURL(`${BASE_URL}/review-order/`);
  await expect(page.locator('body')).toContainText(PRODUCT_NAME);
});

test('a cart older than CART_TTL_MS is not resurrected', async ({ page }) => {
  await login(page);
  await page.goto(`${BASE_URL}/create-order/`);

  // Block the add-to-cart sync so the server-side session cart stays
  // empty — otherwise the earlier successful sync alone would make the
  // reload see a real, non-empty session cart and this test wouldn't
  // exercise the TTL fallback path at all. This reproduces a sync that
  // never landed (e.g. the tab closed/reloaded before the request
  // completed), leaving only the local cart + its timestamp behind.
  await page.route('**/update-cart/', (route) => route.abort());
  await addProductToCartWithoutSubmitting(page);
  await page.unroute('**/update-cart/');

  // Backdate the recorded timestamp past the TTL window, then reload —
  // this is the "genuinely abandoned cart" case c23d6a7 protected against,
  // and the fix must still protect against it.
  await page.evaluate((ttlMs) => {
    for (const key of Object.keys(localStorage)) {
      if (key.endsWith(':updatedAt')) {
        localStorage.setItem(key, String(Date.now() - ttlMs - 1000));
      }
    }
  }, CART_TTL_MS);

  await page.reload();

  await page.click('#cart-drawer-toggle');
  const cartItemsText = await page.locator('#mobile-cart-items').innerText();
  expect(cartItemsText).not.toContain(PRODUCT_NAME);

  await page.goto(`${BASE_URL}/review-order/`);
  await page.waitForURL(`${BASE_URL}/create-order/`);
  await expect(page.locator('body')).toContainText('Your cart is empty');
});

test('a sync failure at Submit shows an error and does not proceed to checkout', async ({ page }) => {
  // Guards against a regression where a failed sync silently "succeeds"
  // and sends the participant to review-order with an empty/stale
  // session cart — this is the failure mode symptom 1 and 3 originally
  // described ("freezes"/"kicked out"), so the fix must fail loudly and
  // stay put instead of proceeding.
  await login(page);
  await page.goto(`${BASE_URL}/create-order/`);
  await addProductToCartWithoutSubmitting(page);

  await page.route('**/update-cart/', (route) => route.abort());

  const dialogPromise = page.waitForEvent('dialog');
  await page.click('#mobile-submit-order');
  const dialog = await dialogPromise;
  expect(dialog.message()).toContain('Error submitting order');
  await dialog.accept();

  // Must still be on create-order, not bounced forward to checkout.
  await expect(page).toHaveURL(`${BASE_URL}/create-order/`);
});
