/**
 * Per-balance budget view of the cart.
 *
 * The food balance (available_balance) is the voucher total and pays for
 * the whole cart, hygiene and Go Fresh included. Hygiene and Go Fresh are
 * caps on how much of it their items may use (product.budget, classified by
 * the server). So the food line counts every item, and the hygiene and Go
 * Fresh lines never show more than is left overall. This mirrors the
 * server's rule in apps/orders/utils/balance_rules.py.
 *
 * Showing only one combined number hid the caps, so a participant with $0
 * hygiene could add hygiene items and only learn at checkout. This hook is
 * the single place the UI derives "what's left in each balance" from. The
 * server's validate-cart remains the authority; these numbers are for live
 * display while the cart changes.
 */
import { useMemo } from 'react';
import { useCartContext, type CartItemData } from '../../providers/CartProvider';
import { useValidation } from '../../providers/ValidationContext';
import type { Balances, BudgetKey, Product } from '../types/api';

export interface BudgetLine {
  key: BudgetKey;
  balance: number;
  spent: number;
  remaining: number;
  isOver: boolean;
}

export interface Budgets {
  /** Food first, then hygiene and Go Fresh — only balances the participant has. */
  lines: BudgetLine[];
  food: BudgetLine;
  isOverAny: boolean;
}

const BALANCE_FIELD: Record<BudgetKey, keyof Balances> = {
  food: 'available_balance',
  hygiene: 'hygiene_balance',
  go_fresh: 'go_fresh_balance',
};

export function computeBudgets(
  balances: Balances,
  items: Pick<CartItemData, 'price' | 'quantity' | 'budget'>[],
): Budgets {
  // Food counts every item; hygiene and Go Fresh count only their own
  const spent: Record<BudgetKey, number> = { food: 0, hygiene: 0, go_fresh: 0 };
  for (const item of items) {
    const cost = (item.price || 0) * (item.quantity || 1);
    spent.food += cost;
    if (item.budget && item.budget !== 'food') spent[item.budget] += cost;
  }

  const line = (key: BudgetKey, leftOverall = Infinity): BudgetLine => {
    const balance = Number(balances[BALANCE_FIELD[key]]) || 0;
    return {
      key,
      balance,
      spent: spent[key],
      remaining: Math.min(Math.max(0, balance - spent[key]), leftOverall),
      isOver: spent[key] > balance,
    };
  };

  const food = line('food');
  const hygiene = line('hygiene', food.remaining);
  // The server only enforces Go Fresh when the participant has a Go Fresh
  // balance (validate-cart skips it at $0), so mirror that here.
  const goFresh = line('go_fresh', food.remaining);
  if (goFresh.balance <= 0) goFresh.isOver = false;

  // Hygiene stays visible even at $0 so a disabled hygiene item has an
  // explanation on screen; Go Fresh only appears when the participant has it.
  const lines = [food, hygiene, ...(goFresh.balance > 0 ? [goFresh] : [])];

  return { lines, food, isOverAny: lines.some((l) => l.isOver) };
}

/**
 * Products the participant cannot buy at all right now. Today that's only
 * hygiene items when the hygiene balance is $0 (product decision 2026-10-19:
 * disable rather than hide, so the participant can see what exists).
 */
export function isBlockedByBudget(product: Pick<Product, 'budget'>, balances: Balances | null): boolean {
  if (!balances) return false;
  return product.budget === 'hygiene' && balances.hygiene_balance <= 0;
}

export const useBudgets = (): Budgets | null => {
  const { balances } = useValidation();
  const { items } = useCartContext();
  return useMemo(() => (balances ? computeBudgets(balances, items) : null), [balances, items]);
};
