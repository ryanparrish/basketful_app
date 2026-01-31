import React from 'react';
import { render, screen } from '@testing-library/react';
import { CartProvider } from 'react-use-cart';
import ParticipantCart from '../components/ParticipantCart';
import { vi } from 'vitest';

vi.mock('react-use-cart', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useCart: vi.fn()
  };
});

test('renders ParticipantCart with empty cart', () => {
  render(
    <CartProvider>
      <ParticipantCart />
    </CartProvider>
  );
  const emptyMessage = screen.getByText(/Your cart is empty/i);
  expect(emptyMessage).to.exist;
});

test('renders ParticipantCart with items', () => {
  const { useCart } = require('react-use-cart');

  useCart.mockReturnValue({
    isEmpty: false,
    totalUniqueItems: 2,
    items: [
      { id: 1, name: 'Item 1', quantity: 1, price: 10 },
      { id: 2, name: 'Item 2', quantity: 2, price: 15 }
    ],
    cartTotal: 40,
    updateItemQuantity: vi.fn(),
    removeItem: vi.fn(),
    emptyCart: vi.fn()
  });

  render(<ParticipantCart />);

  const totalItems = screen.getByText(/Total Items: 2/i);
  expect(totalItems).to.exist;

  const totalPrice = screen.getByText(/Total: \$40/i);
  expect(totalPrice).to.exist;
});