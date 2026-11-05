/**
 * How the cart handles a participant's balances, as
 * POST /api/v1/orders/validate-cart/ reports them
 * (apps/orders/utils/balance_rules.py):
 *
 *   - Food (available_balance) is the voucher total and pays for the whole
 *     cart, hygiene and Go Fresh included.
 *   - Hygiene (hygiene_balance) caps how much of it hygiene items may use.
 *   - Go Fresh (go_fresh_balance) caps how much of it Go Fresh items may use.
 *
 * All three follow the grace setting alike. Going over by more than the
 * program's grace amount is an error naming the balance and the amount
 * over, and blocks checkout. Going over by no more than the grace amount is
 * a warning showing the program's grace message, and checkout stays open.
 * Placing orders is covered in checkout-place-order.spec.ts.
 *
 * Fixture: `python manage.py seed_e2e_participant` (run by global-setup)
 * prices the products against the participant's balances.
 */
import { expect, test } from '@playwright/test';
import {
  OVER_CAP_MARGIN,
  PRODUCTS,
  SMALL_ITEM_PRICE,
  addToCart,
  budgetLeft,
  cartMessage,
  checkoutButton,
  dollars,
  openCart,
  overBudgetBanner,
  readBalances,
  readGraceMessage,
} from './support/cart';

test.beforeEach(async ({ page }) => {
  await page.goto('/products');
});

test.describe('hygiene balance', () => {
  test('going over it names the hygiene balance and blocks checkout', async ({ page }) => {
    await addToCart(page, PRODUCTS.overBudgetHygiene);
    await openCart(page);

    await expect(cartMessage(page, `Hygiene balance exceeded by ${dollars(OVER_CAP_MARGIN)}`)).toBeVisible();
    await expect(page.getByText(/Food balance exceeded/)).toHaveCount(0);
    await expect(checkoutButton(page)).toHaveText('Please fix cart errors');
    await expect(checkoutButton(page)).toBeDisabled();
  });

  test('a hygiene item within it checks out, and the cart shows what is left', async ({ page }) => {
    const balances = await readBalances(page);

    await addToCart(page, PRODUCTS.smallHygiene);
    await openCart(page);

    await expect(page.getByText(/balance exceeded/)).toHaveCount(0);
    await expect(budgetLeft(page, 'Hygiene')).toHaveText(dollars(balances.hygiene - SMALL_ITEM_PRICE));
    // The hygiene item spends the voucher total too
    await expect(budgetLeft(page, 'Food')).toHaveText(dollars(balances.food - SMALL_ITEM_PRICE));
    await expect(checkoutButton(page)).toBeEnabled();

    await checkoutButton(page).click();
    await expect(page).toHaveURL(/\/checkout$/);
    await expect(budgetLeft(page, 'Hygiene')).toHaveText(dollars(balances.hygiene - SMALL_ITEM_PRICE));
  });

  test('food and hygiene that each fit, but together pass the food balance, block checkout', async ({ page }) => {
    // Hygiene is a share of the food balance, not extra money: order
    // submission rejects food + hygiene over available_balance
    // (OrderValidation.validate_order_items, step 3b), so the cart must
    // say so before the participant gets that far.
    await addToCart(page, PRODUCTS.nearBudgetFood);
    await addToCart(page, PRODUCTS.smallHygiene);
    await openCart(page);

    await expect(cartMessage(page, /balance exceeded by/)).toBeVisible();
    await expect(checkoutButton(page)).toBeDisabled();
  });
});

test.describe('Go Fresh balance', () => {
  test('going over its cap beyond grace names Go Fresh and blocks checkout', async ({ page }) => {
    const balances = await readBalances(page);
    expect(balances.goFresh, 'Go Fresh must be enabled for this participant').toBeGreaterThan(0);

    await addToCart(page, PRODUCTS.overBudgetGoFresh);
    await openCart(page);

    await expect(cartMessage(page, `Go Fresh balance exceeded by ${dollars(OVER_CAP_MARGIN)}`)).toBeVisible();
    await expect(page.getByText(/Food balance exceeded/)).toHaveCount(0);
    await expect(checkoutButton(page)).toHaveText('Please fix cart errors');
    await expect(checkoutButton(page)).toBeDisabled();
  });

  test('a Go Fresh item within it checks out', async ({ page }) => {
    await addToCart(page, PRODUCTS.smallGoFresh);
    await openCart(page);

    await expect(page.getByText(/balance exceeded/)).toHaveCount(0);
    await expect(checkoutButton(page)).toBeEnabled();
  });
});

test.describe('grace allowance', () => {
  test('a cart just over the food balance shows the grace message and can check out', async ({ page }) => {
    const graceMessage = await readGraceMessage(page);

    await addToCart(page, PRODUCTS.graceFood);
    await openCart(page);

    await expect(cartMessage(page, graceMessage)).toBeVisible();
    await expect(page.getByText(/balance exceeded/)).toHaveCount(0);
    await expect(checkoutButton(page)).toHaveText('Proceed to Checkout');
    await expect(checkoutButton(page)).toBeEnabled();
    // Inside grace the cart explains the overage; nothing needs removing
    await expect(overBudgetBanner(page)).toHaveCount(0);
  });
});

test.describe('remaining budget', () => {
  test('the cart and checkout show the food balance less the cart total', async ({ page }) => {
    const balances = await readBalances(page);

    await addToCart(page, PRODUCTS.smallFood);
    await openCart(page);
    await expect(budgetLeft(page, 'Food')).toHaveText(dollars(balances.food - SMALL_ITEM_PRICE));

    await checkoutButton(page).click();
    await expect(page).toHaveURL(/\/checkout$/);
    await expect(budgetLeft(page, 'Food')).toHaveText(dollars(balances.food - SMALL_ITEM_PRICE));
  });

  test('Go Fresh items spend the food balance too', async ({ page }) => {
    const balances = await readBalances(page);

    await addToCart(page, PRODUCTS.smallGoFresh);
    await openCart(page);

    await expect(budgetLeft(page, 'Food')).toHaveText(dollars(balances.food - SMALL_ITEM_PRICE));
    await expect(budgetLeft(page, 'Go Fresh')).toHaveText(dollars(balances.goFresh - SMALL_ITEM_PRICE));
  });

  test('an over-budget cart shows nothing left, not a negative amount', async ({ page }) => {
    await addToCart(page, PRODUCTS.overBudgetFood);
    await openCart(page);

    await expect(budgetLeft(page, 'Food')).toHaveText('$0.00');
  });
});
