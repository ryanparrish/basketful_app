/**
 * Per-balance budget view of the cart.
 *
 * A participant has three separate balances — food (available_balance),
 * hygiene and Go Fresh — and each product draws from exactly one of them
 * (product.budget, classified by the server). Showing one combined
 * "available" number hid that, so a participant with $0 hygiene could add
 * hygiene items and only learn at checkout. This hook is the single place
 * the UI derives "what's left in each balance" from.
 *
 * The server's validate-cart remains the authority; these numbers are for
 * live display while the cart changes.
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
  const spent: Record<BudgetKey, number> = { food: 0, hygiene: 0, go_fresh: 0 };
  for (const item of items) {
    spent[item.budget ?? 'food'] += (item.price || 0) * (item.quantity || 1);
  }

  const line = (key: BudgetKey): BudgetLine => {
    const balance = Number(balances[BALANCE_FIELD[key]]) || 0;
    return {
      key,
      balance,
      spent: spent[key],
      remaining: Math.max(0, balance - spent[key]),
      isOver: spent[key] > balance,
    };
  };

  const food = line('food');
  const hygiene = line('hygiene');
  // The server only enforces Go Fresh when the participant has a Go Fresh
  // balance (validate-cart skips it at $0), so mirror that here.
  const goFresh = line('go_fresh');
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
