/**
 * Product cards disable (not hide) hygiene items when the participant has
 * no hygiene balance, so they can't build a cart that will be rejected.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { Balances, Product } from '../../../shared/types/api';

let balances: Balances;
const addItem = vi.fn();

vi.mock('../../../providers/ValidationContext', () => ({
  useValidation: () => ({
    balances,
    getErrorsForProduct: () => [],
    getWarningsForProduct: () => [],
  }),
}));

vi.mock('../../../providers/CartProvider', () => ({
  useCartContext: () => ({ addItem, updateItemQuantity: vi.fn(), removeItem: vi.fn() }),
  useItemInCart: () => ({ isInCart: false, quantity: 0 }),
}));

import { ProductCard } from '../ProductCard';

const product = (overrides: Partial<Product> = {}): Product => ({
  id: 7,
  name: 'Aluminum Foil',
  description: '',
  price: 3.5,
  image: null,
  category: 7,
  category_name: 'Hygiene',
  budget: 'hygiene',
  is_available: true,
  unit: null,
  ...overrides,
});

describe('ProductCard', () => {
  beforeEach(() => {
    addItem.mockReset();
    balances = { available_balance: 40, hygiene_balance: 0, go_fresh_balance: 0, full_balance: 40 };
  });

  it('disables a hygiene item when the hygiene balance is $0, and says why', () => {
    render(<ProductCard product={product()} />);

    expect(screen.getByRole('button', { name: 'Add to cart' })).toBeDisabled();
    expect(screen.getByText('No hygiene balance')).toBeInTheDocument();
  });

  it('allows a hygiene item when there is a hygiene balance', async () => {
    balances.hygiene_balance = 5;
    render(<ProductCard product={product()} />);

    await userEvent.click(screen.getByRole('button', { name: 'Add to cart' }));

    expect(addItem).toHaveBeenCalled();
    expect(screen.queryByText('No hygiene balance')).not.toBeInTheDocument();
  });

  it('leaves food items alone when the hygiene balance is $0', () => {
    render(<ProductCard product={product({ name: 'Beans', budget: 'food', category_name: 'Pantry Food' })} />);

    expect(screen.getByRole('button', { name: 'Add to cart' })).toBeEnabled();
  });
});
