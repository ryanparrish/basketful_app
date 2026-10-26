import { describe, it, expect } from 'vitest';
import { computeBudgets, isBlockedByBudget } from '../useBudgets';
import type { Balances } from '../../types/api';

const balances = (overrides: Partial<Balances> = {}): Balances => ({
  available_balance: 40,
  hygiene_balance: 5,
  go_fresh_balance: 10,
  full_balance: 40,
  ...overrides,
});

describe('computeBudgets', () => {
  it('spends the food balance on every item, and each cap only on its own items', () => {
    const b = computeBudgets(balances(), [
      { price: 2, quantity: 3, budget: 'food' },
      { price: 3.5, quantity: 1, budget: 'hygiene' },
      { price: 4, quantity: 1, budget: 'go_fresh' },
    ]);

    // The vouchers pay for the whole cart: $40 - ($6 + $3.50 + $4)
    expect(b.food.remaining).toBe(26.5);
    expect(b.lines.find((l) => l.key === 'hygiene')?.remaining).toBe(1.5);
    expect(b.lines.find((l) => l.key === 'go_fresh')?.remaining).toBe(6);
    expect(b.isOverAny).toBe(false);
  });

  it('never shows more hygiene or Go Fresh left than is left overall', () => {
    const b = computeBudgets(balances({ available_balance: 10 }), [
      { price: 9, quantity: 1, budget: 'food' },
    ]);

    expect(b.food.remaining).toBe(1);
    expect(b.lines.find((l) => l.key === 'hygiene')?.remaining).toBe(1);
    expect(b.lines.find((l) => l.key === 'go_fresh')?.remaining).toBe(1);
  });

  it('flags the food balance when hygiene and Go Fresh push the cart over it', () => {
    const b = computeBudgets(balances({ available_balance: 10 }), [
      { price: 5, quantity: 1, budget: 'food' },
      { price: 3, quantity: 1, budget: 'hygiene' },
      { price: 4, quantity: 1, budget: 'go_fresh' },
    ]);

    expect(b.food.isOver).toBe(true);
    expect(b.lines.find((l) => l.key === 'hygiene')?.isOver).toBe(false);
    expect(b.lines.find((l) => l.key === 'go_fresh')?.isOver).toBe(false);
  });

  it('flags the specific balance that is exceeded', () => {
    const b = computeBudgets(balances({ hygiene_balance: 0 }), [
      { price: 3.5, quantity: 1, budget: 'hygiene' },
    ]);

    const hygiene = b.lines.find((l) => l.key === 'hygiene');
    expect(hygiene?.isOver).toBe(true);
    expect(hygiene?.remaining).toBe(0);
    expect(b.food.isOver).toBe(false);
    expect(b.isOverAny).toBe(true);
  });

  it('treats items saved before budget existed as food', () => {
    const b = computeBudgets(balances(), [{ price: 10, quantity: 1 }]);
    expect(b.food.spent).toBe(10);
  });

  it('hides Go Fresh and never flags it when the participant has no Go Fresh balance', () => {
    // validate-cart only enforces Go Fresh when the balance is > 0
    const b = computeBudgets(balances({ go_fresh_balance: 0 }), [
      { price: 4, quantity: 1, budget: 'go_fresh' },
    ]);

    expect(b.lines.map((l) => l.key)).toEqual(['food', 'hygiene']);
    expect(b.isOverAny).toBe(false);
  });

  it('always lists hygiene, even at $0, so disabled hygiene items are explained', () => {
    const b = computeBudgets(balances({ hygiene_balance: 0 }), []);
    expect(b.lines.map((l) => l.key)).toContain('hygiene');
  });
});

describe('isBlockedByBudget', () => {
  it('blocks hygiene products when the hygiene balance is $0', () => {
    expect(isBlockedByBudget({ budget: 'hygiene' }, balances({ hygiene_balance: 0 }))).toBe(true);
  });

  it('allows hygiene products when there is a hygiene balance', () => {
    expect(isBlockedByBudget({ budget: 'hygiene' }, balances({ hygiene_balance: 5 }))).toBe(false);
  });

  it('never blocks food or Go Fresh products', () => {
    const empty = balances({ available_balance: 0, go_fresh_balance: 0, hygiene_balance: 0 });
    expect(isBlockedByBudget({ budget: 'food' }, empty)).toBe(false);
    expect(isBlockedByBudget({ budget: 'go_fresh' }, empty)).toBe(false);
  });

  it('does not block before balances have loaded', () => {
    expect(isBlockedByBudget({ budget: 'hygiene' }, null)).toBe(false);
  });
});
