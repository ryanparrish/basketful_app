import React from 'react';
import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import { useCart } from 'react-use-cart';
import ParticipantCart from '../components/ParticipantCart';

vi.mock('react-use-cart', () => ({
  useCart: vi.fn(),
}));

test('renders ParticipantCart with empty cart', () => {
  vi.mocked(useCart).mockReturnValue({
    isEmpty: true,
    totalUniqueItems: 0,
    items: [],
    cartTotal: 0,
    updateItemQuantity: vi.fn(),
    removeItem: vi.fn(),
    emptyCart: vi.fn(),
  });

  render(<ParticipantCart />);
  expect(screen.getByText(/Your cart is empty/i)).toBeDefined();
});

test('renders ParticipantCart with items', () => {
  vi.mocked(useCart).mockReturnValue({
    isEmpty: false,
    totalUniqueItems: 2,
    items: [
      { id: 1, name: 'Item 1', quantity: 1, price: 10 },
      { id: 2, name: 'Item 2', quantity: 2, price: 15 },
    ],
    cartTotal: 40,
    updateItemQuantity: vi.fn(),
    removeItem: vi.fn(),
    emptyCart: vi.fn(),
  });

  render(<ParticipantCart />);
  expect(screen.getByText(/Total Items: 2/i)).toBeDefined();
  expect(screen.getByText(/Total: \$40/i)).toBeDefined();
});