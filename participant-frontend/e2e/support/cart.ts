/**
 * Shared steps for the cart e2e specs. Product names match
 * apps/account/management/commands/seed_e2e_participant.py.
 */
import { expect, type Page } from '@playwright/test';

export const PRODUCTS = {
  overBudgetFood: 'E2E Over-Budget Test Item',
  graceFood: 'E2E Grace Test Item',
  nearBudgetFood: 'E2E Near-Budget Food Item',
  smallFood: 'E2E Small Food Item',
  overBudgetHygiene: 'E2E Over-Budget Hygiene Item',
  smallHygiene: 'E2E Small Hygiene Item',
  overBudgetGoFresh: 'E2E Over-Budget Go Fresh Item',
  smallGoFresh: 'E2E Small Go Fresh Item',
} as const;

export const SMALL_ITEM_PRICE = 5;
export const OVER_BUDGET_PRICE = 999.99;
/** How far the over-cap hygiene and Go Fresh items go past their cap */
export const OVER_CAP_MARGIN = 5;

export interface ParticipantBalances {
  food: number;
  hygiene: number;
  goFresh: number;
}

/** The balances the cart is checked against, read the way the app reads them */
export async function readBalances(page: Page): Promise<ParticipantBalances> {
  const response = await page.request.get('/api/v1/participants/me/balances/');
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  return {
    food: Number(body.available_balance),
    hygiene: Number(body.hygiene_balance),
    goFresh: Number(body.go_fresh_balance),
  };
}

export async function readGraceMessage(page: Page): Promise<string> {
  const response = await page.request.get('/api/v1/settings/program-config/current/');
  expect(response.ok()).toBeTruthy();
  const settings = await response.json();
  expect(settings.grace_enabled, 'these specs expect the grace allowance to be on').toBe(true);
  return settings.grace_message;
}

/** Adds one of a product and waits for the cart's debounced backend validation */
export async function addToCart(page: Page, productName: string) {
  await page.getByPlaceholder('Search products...').fill(productName);
  const validated = page.waitForResponse(
    response => response.url().includes('/orders/validate-cart/'),
    { timeout: 10_000 },
  );
  await page.getByRole('button', { name: 'Add to cart' }).click();
  await validated;
}

export async function openCart(page: Page) {
  await page.getByRole('button', { name: 'Open cart' }).click();
  await expect(page.getByText(/^Cart \(\d+\)$/)).toBeVisible();
}

export function checkoutButton(page: Page) {
  return page.getByRole('button', { name: /^(Proceed to Checkout|Please fix cart errors|Validating cart\.\.\.)$/ });
}

const BUDGET_LABELS = {
  Food: 'Left to spend',
  Hygiene: 'Hygiene left',
  'Go Fresh': 'Go Fresh left',
} as const;

/**
 * The amount beside one balance in the list of what's left (BudgetSummary),
 * as the cart drawer and checkout show it, e.g. "Left to spend  $95.00".
 */
export function budgetLeft(page: Page, name: keyof typeof BUDGET_LABELS) {
  return page
    .getByTestId('budget-summary')
    .getByText(BUDGET_LABELS[name], { exact: true })
    .locator('xpath=following-sibling::*[1]');
}

/**
 * A validation message in the open cart drawer. The cart shows each one in
 * its summary and again on the cart lines that caused it, so take the first.
 */
export function cartMessage(page: Page, text: string | RegExp) {
  return page.getByRole('dialog').getByText(text).first();
}

export function overBudgetBanner(page: Page) {
  return page.getByText('Your cart exceeds your available budget. Please remove some items.');
}

export function dollars(amount: number) {
  return `$${amount.toFixed(2)}`;
}
