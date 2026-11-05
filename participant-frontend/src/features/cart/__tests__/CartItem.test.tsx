/**
 * The cart flags the exact line that's blocking checkout, using the
 * product_ids validate-cart attaches to each violation.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ValidationProvider } from '../../../providers/ValidationContext';
import type { CartItemData } from '../../../providers/CartProvider';

const violation = {
  type: 'balance',
  severity: 'error' as const,
  message: 'Hygiene balance exceeded by $3.50',
  budget: 'hygiene' as const,
  product_ids: [2],
};

const items: CartItemData[] = [
  { id: 'product-1', productId: 1, name: 'Beans', price: 1.5, quantity: 1, budget: 'food', available: true },
  { id: 'product-2', productId: 2, name: 'Aluminum Foil', price: 3.5, quantity: 1, budget: 'hygiene', available: true },
];

vi.mock('../../../shared/api/endpoints', () => ({
  validateCart: vi.fn(async () => ({ valid: false, violations: [violation] })),
  getProgramConfig: vi.fn(async () => ({})),
  getBalances: vi.fn(async () => ({
    available_balance: 40, hygiene_balance: 0, go_fresh_balance: 0, full_balance: 40,
  })),
}));

vi.mock('../../../shared/hooks/useOrderWindow', () => ({
  useOrderWindow: () => ({ isOpen: true, windowStatus: 'open', isLoading: false }),
}));

vi.mock('../../../providers/CartProvider', () => ({
  useCartContext: () => ({
    items,
    isEmpty: false,
    getApiCartItems: () => items.map((i) => ({ product_id: i.productId, quantity: i.quantity })),
    updateItemQuantity: vi.fn(),
    removeItem: vi.fn(),
  }),
}));

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CartItem } from '../CartItem';

function renderCart() {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ValidationProvider>
        {items.map((item) => (
          <div key={item.id} data-testid={item.id}>
            <CartItem item={item} />
          </div>
        ))}
      </ValidationProvider>
    </QueryClientProvider>
  );
}

describe('CartItem', () => {
  it('shows the violation on the line that caused it, not on every line', async () => {
    renderCart();

    const foil = screen.getByTestId('product-2');
    expect(await screen.findByText('Hygiene balance exceeded by $3.50', {}, { timeout: 3000 }))
      .toBeInTheDocument();
    expect(foil).toHaveTextContent('Hygiene balance exceeded by $3.50');
    expect(screen.getByTestId('product-1')).not.toHaveTextContent('exceeded');
  });

  it('disables + on a hygiene line when there is no hygiene balance', async () => {
    renderCart();
    // Wait for balances to load into the validation context.
    await screen.findByText('Hygiene balance exceeded by $3.50', {}, { timeout: 3000 });

    const [beansPlus, foilPlus] = screen.getAllByRole('button', { name: 'Increase quantity' });
    expect(beansPlus).toBeEnabled();
    expect(foilPlus).toBeDisabled();
  });
});
